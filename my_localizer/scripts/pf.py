#!/usr/bin/env python

""" This is the Judy and Lauren's code for localization project 
To run, type the following in terminal
    roslaunch my_localizer test.launch map_file:=path to the yaml file
""" 


import rospy

from std_msgs.msg import Header, String
from sensor_msgs.msg import LaserScan
from geometry_msgs.msg import PoseStamped, PoseWithCovarianceStamped, PoseArray, Pose, Point, Quaternion
from nav_msgs.srv import GetMap
from copy import deepcopy

import tf
from tf import TransformListener
from tf import TransformBroadcaster
from tf.transformations import euler_from_quaternion, rotation_matrix, quaternion_from_matrix
from random import gauss
from scipy.stats import norm

import math
import time

import numpy as np
from numpy.random import random_sample
from sklearn.neighbors import NearestNeighbors
from occupancy_field import OccupancyField

from helper_functions import (convert_pose_inverse_transform,
                              convert_translation_rotation_to_pose,
                              convert_pose_to_xy_and_theta,
                              angle_diff)

class Particle(object):
    """ Represents a hypothesis (particle) of the robot's pose consisting of x,y and theta (yaw)
        Attributes:
            x: the x-coordinate of the hypothesis relative to the map frame
            y: the y-coordinate of the hypothesis relative ot the map frame
            theta: the yaw of the hypothesis relative to the map frame
            w: the particle weight (the class does not ensure that particle weights are normalized)
    """

    def __init__(self,x=0.0,y=0.0,theta=0.0,w=1.0):
        """ Construct a new Particle
            x: the x-coordinate of the hypothesis relative to the map frame
            y: the y-coordinate of the hypothesis relative ot the map frame
            theta: the yaw of the hypothesis relative to the map frame
            w: the particle weight (the class does not ensure that particle weights are normalized """
        self.w = w
        self.theta = theta
        self.x = x
        self.y = y

    def as_pose(self):
        """ A helper function to convert a particle to a geometry_msgs/Pose message """
        orientation_tuple = tf.transformations.quaternion_from_euler(0,0,self.theta)
        return Pose(position=Point(x=self.x,y=self.y,z=0), orientation=Quaternion(x=orientation_tuple[0], y=orientation_tuple[1], z=orientation_tuple[2], w=orientation_tuple[3]))

    # TODO: define additional helper functions if needed

class ParticleFilter:
    """ The class that represents a Particle Filter ROS Node
        Attributes list:
            initialized: a Boolean flag to communicate to other class methods that initializaiton is complete
            base_frame: the name of the robot base coordinate frame (should be "base_link" for most robots)
            map_frame: the name of the map coordinate frame (should be "map" in most cases)
            odom_frame: the name of the odometry coordinate frame (should be "odom" in most cases)
            scan_topic: the name of the scan topic to listen to (should be "scan" in most cases)
            n_particles: the number of particles in the filter
            d_thresh: the amount of linear movement before triggering a filter update
            a_thresh: the amount of angular movement before triggering a filter update
            laser_max_distance: the maximum distance to an obstacle we should use in a likelihood calculation
            pose_listener: a subscriber that listens for new approximate pose estimates (i.e. generated through the rviz GUI)
            particle_pub: a publisher for the particle cloud
            laser_subscriber: listens for new scan data on topic self.scan_topic
            tf_listener: listener for coordinate transforms
            tf_broadcaster: broadcaster for coordinate transforms
            particle_cloud: a list of particles representing a probability distribution over robot poses
            current_odom_xy_theta: the pose of the robot in the odometry frame when the last filter update was performed.
                                   The pose is expressed as a list [x,y,theta] (where theta is the yaw)
            map: the map we will be localizing ourselves in.  The map should be of type nav_msgs/OccupancyGrid
    """
    def __init__(self):
        self.initialized = False        # make sure we don't perform updates before everything is setup
        rospy.init_node('pf')           # tell roscore that we are creating a new node named "pf"

        self.base_frame = "base_link"   # the frame of the robot base
        self.map_frame = "map"          # the name of the map coordinate frame
        self.odom_frame = "odom"        # the name of the odometry coordinate frame
        self.scan_topic = "scan"        # the topic where we will get laser scans from

        self.n_particles = 100          # the number of particles to use
        self.select_particle_ratio = 10  # The ratio of total particles to selected particles in each resample
        self.num_resamples = self.n_particles/self.select_particle_ratio    #number of particles to keep when resampling. 

        #Good d_thresh: 0.2
        self.d_thresh = 0.2             # the amount of linear movement before performing an update
        self.a_thresh = math.pi/6       # the amount of angular movement before performing an update

        self.laser_max_distance = 2.5   # maximum penalty to assess in the likelihood field model

        # Setup pubs and subs
        self.robot_pose_pub = rospy.Publisher("robot_pose", Pose, queue_size=10)
        # pose_listener responds to selection of a new approximate robot location (for instance using rviz)
        self.pose_listener = rospy.Subscriber("initialpose", PoseWithCovarianceStamped, self.update_initial_pose)
        # publish the current particle cloud.  This enables viewing particles in rviz.
        self.particle_pub = rospy.Publisher("particlecloud", PoseArray, queue_size=10)

        # laser_subscriber listens for data from the lidar
        self.laser_subscriber = rospy.Subscriber(self.scan_topic, LaserScan, self.scan_received)

        # enable listening for and broadcasting coordinate transforms
        self.tf_listener = TransformListener()
        self.tf_broadcaster = TransformBroadcaster()

        self.particle_cloud = []

        self.current_odom_xy_theta = []     #current position of ourself in odom frame

        # request the map from the map server, the map should be of type nav_msgs/OccupancyGrid
        get_map_from_server = rospy.ServiceProxy('static_map', GetMap) # 'static map' is the service that map_server publishes to.
        self.map = get_map_from_server()
        print 'got map' #Do not print the map itself, it is huge

        # Create our occupancy field to reference later using the map we got
        self.occupancy_field = OccupancyField(self.map.map)
        print 'created occupancy field'

        self.initialized = True

    def update_robot_pose(self):
        """ Update the estimate of the robot's pose given the updated particles.
            There are two logical methods for this:
                (1): compute the mean pose <--- currently doing this option
                (2): compute the most likely pose (i.e. the mode of the distribution)
                (3): Above a likelihood threshold, compute the mean of those
                (4): Differentiate between clusters, compute mean in most likely cluster
        """
        # first make sure that the particle weights are normalized
        self.normalize_particles()
        choose = "mean"  #Which strategy to use 

        if choose =="mode":
            #Use the pose of the most likely particle
            curr_weights = [i.w for i in self.particle_cloud]
            idx = curr_weights.index(max(curr_weights))
            mmPos_x = self.particle_cloud[idx].x
            mmPos_y = self.particle_cloud[idx].y
            average_angle = self.particle_cloud[idx].theta

            # #Code to use the mean of the most likely particles: 
            # for i in range(0, self.num_resamples):
            #     most_common_particles.append(self.particle_cloud[idx])
            #     curr_weights.pop(idx)
        elif choose == "mean":
            #Use the mean of all particles:
            most_common_particles = []
            for particle in self.particle_cloud:
                if particle.w: #if the particle exists..... change me later to account for modes!
                    most_common_particles.append(particle)
            mmPos_x = np.mean([i.x for i in most_common_particles])        #mean of modes of x positions
            mmPos_y = np.mean([i.y for i in most_common_particles])        #mean of modes of y positions

            angle_x = 0
            angle_y = 0
            #Can not just average angles because (350, 10) would give 180. Thus, converting them to x,y
            #and adding up x and y instead then converting back
            for particle in most_common_particles:
                angle_x += math.cos(particle.theta)    #particle.theta is in radians
                angle_y += math.sin(particle.theta)    #particle.theta is in radians
            angle_x/=len(most_common_particles)
            angle_y/=len(most_common_particles)
            average_angle = math.atan2(angle_y, angle_x)  

        orientation_tuple = tf.transformations.quaternion_from_euler(0,0,average_angle) #converts theta to quaternion
        self.robot_pose = Pose(position=Point(x=mmPos_x,y=mmPos_y,z=0),orientation=Quaternion(x=orientation_tuple[0], y=orientation_tuple[1], z=orientation_tuple[2], w=orientation_tuple[3]))

    def update_particles_with_odom(self, msg):
        """ Update the particles using the newly given odometry pose.
            The function computes the value delta which is a tuple (x,y,theta)
            that indicates the change in position and angle between the odometry
            when the particles were last updated and the current odometry.

            msg: this is not really needed to implement this, but is here just in case. <-- ?
        """
        new_odom_xy_theta = convert_pose_to_xy_and_theta(self.odom_pose.pose)
        # compute the change in x,y,theta since our last update
        if self.current_odom_xy_theta:
            old_odom_xy_theta = self.current_odom_xy_theta
            delta = (new_odom_xy_theta[0] - self.current_odom_xy_theta[0],
                     new_odom_xy_theta[1] - self.current_odom_xy_theta[1],
                     angle_diff(new_odom_xy_theta[2], self.current_odom_xy_theta[2]))

            self.current_odom_xy_theta = new_odom_xy_theta
        else:
            self.current_odom_xy_theta = new_odom_xy_theta
            return

        #modify particles using delta
        dx = delta[0]
        dy = delta[1]
        dtheta = delta[2]

        #Figure out how much the robot moved relative to its original angle
        angle_travel = math.atan2(dy,dx) #Angle of travel wrpt odom frame
        r1 = angle_travel-self.current_odom_xy_theta[2]   #Rotation 1 to face toward the direction of movement
        r2 = dtheta-r1  #Rotation 2 to final theta
        d = math.sqrt(dy**2+dx**2) #Distance travelled

        #Create a standard deviation proportional to each delta
        # Increase or decrease the constants below based on confidence in odom, can have scales different for theta and x, y
        sigma_d = d*0.3 #Good constant: 0.2
        sigma_theta = dtheta*0.5 #good constant: 0.15

        #update each particle using a normal distribution
        for p in self.particle_cloud:
            p.theta+=r1
            noisy_d = gauss(d,sigma_d)
            p.x+=noisy_d*math.cos(p.theta)
            p.y+=noisy_d*math.sin(p.theta)
            p.theta+=gauss(r2,sigma_theta)

        # For added difficulty: Implement sample_motion_odometry (Prob Rob p 136) <-- ?

    def map_calc_range(self,x,y,theta):
        """ Difficulty Level 3: implement a ray tracing likelihood model... Let me know if you are interested """
        # TO-DO: nothing, unless you want to try this alternate likelihood model
        pass

    def resample_particles(self):
        """ Resample the particles according to the new particle weights.
            The weights stored with each particle should define the probability that a particular
            particle is selected in the resampling step.  You may want to make use of the given helper
            function draw_random_sample.
        """
        # make sure the distribution is normalized
        self.normalize_particles()
        # return
        #initialize a new cloud to be adding selected particles to
        new_cloud = []
        num_top_picks = self.num_resamples/2 #ensure the X most likely particles get added to the new cloud.
        curr_weights = [i.w for i in self.particle_cloud]

        print curr_weights[0:num_top_picks]

        #Make sure top weighted particles are in new cloud.
        for i in range(0, num_top_picks):
            idx = curr_weights.index(max(curr_weights))
            new_cloud.append(self.particle_cloud[idx])
            self.particle_cloud.pop(idx) #pop(id) removes the element at the index, remove(x) delete the element x
            curr_weights.pop(idx)

        #Add other particles at probability-biased "random"
        self.normalize_particles()
        curr_weights = [i.w for i in self.particle_cloud]
        new_cloud.extend(ParticleFilter.draw_random_sample(self.particle_cloud, curr_weights, self.num_resamples-num_top_picks))

        #set particle cloud to be current, but multiplied
        self.particle_cloud = []
        for i in range(self.select_particle_ratio):
            self.particle_cloud.extend(deepcopy(new_cloud))

        print "length of particle cloud", len(self.particle_cloud) 

        #Add noise: modify particles using sigma
        #Good sigma_scale: 0.2
        sigma_scale = 0.2 # Increase or decrease this based on confidence in odom, can have scales different for theta and x, y
        sigma_x = sigma_scale
        sigma_y = sigma_scale
        sigma_theta = sigma_scale*0.5 #Good multiplier: 0.5

        #update each particle using a normal distribution around each delta
        for p in self.particle_cloud:
            p.x+=gauss(0,sigma_x)
            p.y+=gauss(0,sigma_y)
            p.theta+=gauss(0,sigma_theta)


    def update_particles_with_laser(self, msg):
        """ Updates the particle weights in response to the scan contained in the msg
            msg: Laser scan message in base_link frame (technically in base_laser_link, but we can just consider it to be in base_link"""
        for p in self.particle_cloud: #For each particle:
            prob_sum = 0
            # for i,d in enumerate(msg.ranges[0:360:2]): # i is the angle index and d is the distance
            for i,d in enumerate(msg.ranges):
                #Map each laser scan measurement of the particle into a location in x, y, map frame
                if d == 0:
                    continue #Got an invalid measurement
                x = p.x + d*math.cos(math.radians(i)+p.theta) #Adding the angle and position of the particle to account for transformation from base_particle to map
                y = p.y + d*math.sin(math.radians(i)+p.theta)

                #give each x,y position into occupancy field and get back a distance to the closest obstacle point
                closest_dist = self.occupancy_field.get_closest_obstacle_distance(x,y)
                if not closest_dist>0:
                    continue #Ignore nans
                #Find the probablity of seeing that laser scan at the particle's position
                p_measurement = norm.pdf(closest_dist,loc = 0, scale = 0.005) #Using scipy's norm. loc is center, scale is sigma
                #Good p_measurement standard deviation: 0.005
                #Add this probablity to the total probablity of the particle
                prob_sum += p_measurement**3
            #Update the weight of the particles
            p.w = prob_sum 

    @staticmethod
    def weighted_values(values, probabilities, size):
        """ Return a random sample of size elements from the set values with the specified probabilities
            values: the values to sample from (numpy.ndarray)
            probabilities: the probability of selecting each element in values (numpy.ndarray)
            size: the number of samples
        """
        bins = np.add.accumulate(probabilities)
        return values[np.digitize(random_sample(size), bins)]

    @staticmethod
    def draw_random_sample(choices, probabilities, n):
        """ Return a random sample of n elements from the set choices with the specified probabilities
            choices: the values to sample from represented as a list
            probabilities: the probability of selecting each element in choices represented as a list
            n: the number of samples
        """
        values = np.array(range(len(choices)))
        probs = np.array(probabilities)
        bins = np.add.accumulate(probs)
        inds = values[np.digitize(random_sample(n), bins)]
        samples = []
        for i in inds:
            samples.append(deepcopy(choices[int(i)]))
        return samples

    def update_initial_pose(self, msg):
        """ Callback function to handle re-initializing the particle filter based on a pose estimate.
            These pose estimates could be generated by another ROS Node or could come from the rviz GUI """
        xy_theta = convert_pose_to_xy_and_theta(msg.pose.pose)
        self.initialize_particle_cloud(xy_theta)
        self.fix_map_to_odom_transform(msg)

    def initialize_particle_cloud(self, xy_theta=None):
        """ Initialize the particle cloud.
            Arguments
            xy_theta: a triple consisting of the mean x, y, and theta (yaw) to initialize the
                      particle cloud around.  If this input is ommitted, the odometry will be used
            Particles are created based on a normal distribution around the initial position using standard deviation of sigma for x and y
            and sigma_theta for theta"""
        if xy_theta == None:
            xy_theta = convert_pose_to_xy_and_theta(self.odom_pose.pose)
        self.particle_cloud = []

        sigma = 1 
        sigma_theta = 1 
        for i in range(1,self.n_particles):
            x = gauss(xy_theta[0],sigma)
            y = gauss(xy_theta[1],sigma)
            theta = gauss(xy_theta[2],sigma_theta)
            self.particle_cloud.append(Particle(x,y,theta))

        self.normalize_particles()
        self.update_robot_pose()

    def normalize_particles(self):
        """ Make sure the particle weights define a valid distribution (i.e. sum to 1.0) """
        weight_sum = 0
        for p in self.particle_cloud:
            weight_sum+=p.w
        print "weight sum", weight_sum
        for p in self.particle_cloud:
            p.w = p.w * 1.0 / weight_sum

    def publish_particles(self, msg):
        particles_conv = []
        for p in self.particle_cloud:
            particles_conv.append(p.as_pose())
        # actually send the message so that we can view it in rviz
        self.particle_pub.publish(PoseArray(header=Header(stamp=rospy.Time.now(),
                                            frame_id=self.map_frame),
                                  poses=particles_conv))

    def scan_received(self, msg):
        """ This is the default logic for what to do when processing scan data.
            Feel free to modify this, however, I hope it will provide a good
            guide.  The input msg is an object of type sensor_msgs/LaserScan """
        if not(self.initialized):
            # wait for initialization to complete
            return

        if not(self.tf_listener.canTransform(self.base_frame,msg.header.frame_id,msg.header.stamp)):
            # need to know how to transform the laser to the base frame
            # this will be given by either Gazebo or neato_node
            return

        if not(self.tf_listener.canTransform(self.base_frame,self.odom_frame,msg.header.stamp)):
            # need to know how to transform between base and odometric frames
            # this will eventually be published by either Gazebo or neato_node
            return

        # calculate pose of laser relative to the robot base
        p = PoseStamped(header=Header(stamp=rospy.Time(0),
                                      frame_id=msg.header.frame_id))
        self.laser_pose = self.tf_listener.transformPose(self.base_frame,p)

        # find out where the robot thinks it is based on its odometry
        p = PoseStamped(header=Header(stamp=msg.header.stamp,
                                      frame_id=self.base_frame),
                        pose=Pose())
        self.odom_pose = self.tf_listener.transformPose(self.odom_frame, p)
        # store the the odometry pose in a more convenient format (x,y,theta)
        new_odom_xy_theta = convert_pose_to_xy_and_theta(self.odom_pose.pose)

        if not(self.particle_cloud):
            # now that we have all of the necessary transforms we can update the particle cloud
            self.initialize_particle_cloud()
            # cache the last odometric pose so we can only update our particle filter if we move more than self.d_thresh or self.a_thresh
            self.current_odom_xy_theta = new_odom_xy_theta
            # update our map to odom transform now that the particles are initialized
            self.fix_map_to_odom_transform(msg)
        elif (math.fabs(new_odom_xy_theta[0] - self.current_odom_xy_theta[0]) > self.d_thresh or
              math.fabs(new_odom_xy_theta[1] - self.current_odom_xy_theta[1]) > self.d_thresh or
              math.fabs(new_odom_xy_theta[2] - self.current_odom_xy_theta[2]) > self.a_thresh):
            # we have moved far enough to do an update!
            self.update_particles_with_odom(msg)    # update based on odometry
            self.update_particles_with_laser(msg)   # update based on laser scan
            self.update_robot_pose()                # update robot's pose
            self.resample_particles()               # resample particles to focus on areas of high density
            self.fix_map_to_odom_transform(msg)     # update map to odom transform now that we have new particles
        # publish particles (so things like rviz can see them)
        self.publish_particles(msg)

    def fix_map_to_odom_transform(self, msg):
        """ This method constantly updates the offset of the map and
            odometry coordinate systems based on the latest results from
            the localizer
            TODO: if you want to learn a lot about tf, reimplement this... I can provide
                  you with some hints as to what is going on here. """
        (translation, rotation) = convert_pose_inverse_transform(self.robot_pose)
        p = PoseStamped(pose=convert_translation_rotation_to_pose(translation,rotation),
                        header=Header(stamp=msg.header.stamp,frame_id=self.base_frame))
        self.tf_listener.waitForTransform(self.base_frame, self.odom_frame, msg.header.stamp, rospy.Duration(1.0))
        self.odom_to_map = self.tf_listener.transformPose(self.odom_frame, p)
        (self.translation, self.rotation) = convert_pose_inverse_transform(self.odom_to_map.pose)

    def broadcast_last_transform(self):
        """ Make sure that we are always broadcasting the last map
            to odom transformation.  This is necessary so things like
            move_base can work properly. """
        if not(hasattr(self,'translation') and hasattr(self,'rotation')):
            return
        self.tf_broadcaster.sendTransform(self.translation,
                                          self.rotation,
                                          rospy.get_rostime(),
                                          self.odom_frame,
                                          self.map_frame)

if __name__ == '__main__':
    n = ParticleFilter()
    r = rospy.Rate(5)

    while not(rospy.is_shutdown()):
        # in the main loop all we do is continuously broadcast the latest map to odom transform
        n.broadcast_last_transform()
        r.sleep()
