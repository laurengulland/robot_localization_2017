**your ROS package create a file to hold your project writeup. Any format is fine (markdown, word, pdf, etc.). Your writeup should touch on the following topics:**
  ~~1. What was the goal of your project?~~
  2. How did you solve the problem? (Note: this doesn't have to be super-detailed, you should try to explain what you did at a high-level so that others in the class could reasonably understand what you did).
  ~~3. Describe a design decision you had to make when working on your project and what you ultimately did (and why)? These design decisions could be particular choices for how you implemented some part of an algorithm or perhaps a decision regarding which of two external packages to use in your project.~~
  ~~4. What if any challenges did you face along the way?~~
  ~~5. What would you do to improve your project if you had more time?~~
  6. Did you learn any interesting lessons for future robotic programming projects? These could relate to working on robotics projects in teams, working on more open-ended (and longer term) problems, or any other relevant topic.


# Project Overview
This project was completed by Judy Xu and Lauren Gulland for Paul Ruvolo's Computational Robotics class at Olin College of Engineering in Spring 2017. The goal of this project was to build fluency with ROS, understand particle filtering and robot localization, and learn more about building, writing, and understanding algorithms for robotics.

# Project Implementation 
We implemented our particle filter as follows: 
  _Some stuff here_
  _How did you solve the problem? (Note: this doesn't have to be super-detailed, you should try to explain what you did at a high-level so that others in the class could reasonably understand what you did)._
  
You can see our model's performance here:
![Working Base Model](https://github.com/laurengulland/robot_localization_2017/blob/master/my_localizer/videos/ac109_1_good_initial.gif)

## Particle Resampling 
One interesting decision we made while designing our particle filter was how to resample our particles in response to calculating different weights for them all. Obvious answers to this include keeping only the particles in the most common position of the pack and eliminating outliers, or semi-randomly choosing to keep particles and letting their weights determine their likelihood to be kept or eliminated. We decided to combine these methods early on in our code design, and created a resampling mechanism that automatically kept a number of the top-weighted particles and then semi-randomly (accounting for weights) chose from the rest to fill a certain quota of particles we would keep. We then added varying amounts of noise to this core set of kept particles to backfill the rest of our cloud, which gave us the continued variation to help in recovering from imperfect weighting and updating.

## Determining robot pose from particles
One thing we would have liked to work on to take this one step further is implementing cluster tracking. By accounting for the possibility of the particles dividing into clusters (like you see on the map below), we would have been able to adjust for situations like these without just taking the mean of the top weighted particles to find robot pose.
![Clustering Problems](https://github.com/laurengulland/robot_localization_2017/blob/master/my_localizer/videos/particle_filter_cluster.png)

## Updating particles with laser
We chose a simple method of updating the weights of the particles with laser. First, we got the closest distance to an obstacle in the map from Occupancy field for each measurement of each particle. Based on this closest distance, we calculated the probability using a normal distribution with a very small standard deviation. We then added the cube of each measurement probablity up for each particle and that is their weight. We used the cube based on the ROS particle filter model. One important decision we made is to use all the laser measurements (360 of them). This really improved the accuracy of our particle filter, and we compensated for the increase in code running time by decreasing the number of particles to 100. For a complicated environment, 100 particles might still be too much, so it needs to be further decreased. We also ignored NaN values and invalid values. 

## Updating particles with Odometry 


## Adapting to Inaccurate Starting Positions
One additional feature that we were interested in is the ability to recover from an inaccurate starting position. In the gif below, you can see that despite being given a very incorrect heading and a mildly incorrect x-y position, the model recovers well in about 5 seconds by scattering particles much more randomly until they start returning higher confidence in their placement, and then honing down to a more reasonable amount of positional noise when the model is more confident it's in the right place.
![Recovering from an inaccurate initial position](https://github.com/laurengulland/robot_localization_2017/blob/master/my_localizer/videos/ac109_1_bad_initial.gif "animation")

# Process, Lessons, and Improvements

One challenge we ran into along the way was making sure our static and dynamic coordinate transforms were correct. In the beginning in Update particles with Odom we didn't use the relative movement with respect to the robot's pose to update the particles, and our particles just moved in different directions from the robot. This should have been a small thing, but definitely tripped us up because we weren't actively looking for it or thinking about it when writing our code initially, so we didn't get it quite right. Thankfully, with a bit of help, we got it working really well, but we should have been more aware of all the things we would have to be juggling when starting to dive into code development. 

Another challenge we faced was aliasing. In resample particles, we tripled a particle list and forgot to do a deep copy. This resulted in modifying the same particle 3 times in normalizing particles and we kept getting weights that are huge. We solved this problem by using deep copy with a for loop. 

Lastly we had some difficulties tuning our particle filter. We started by tuning each noise parameter but adding noise just seemed to worsen the performance. Then we tried resampling to fewer particles and thar helped a little. Finally when we were about to give up in frustration we chaged from using each second laser scan measurement to using all of them. Suddenly our particle filter worked really well. After this, increasing noise improved the ability to recover from deviations.

In addition to the improvement of cluster tracking mentioned above, we would have liked to dive more into getting our own map working. We created our own map and bag file to throw a different set of data at our model to see how it responds, but unfortunately it doesn't have a map_pose so we can not determine the performance of our particle filter on it. However, our particle filter did create a TimeOut Error when run on our own map. I think this is because in our own map all 360 degrees have a valid laser scan and that takes too much time to process. Thus, in the future it might be good to dynamically set the number of particles to reduce runtime. For example, if it takes too long to update with laser, we either decrease the number of particles or look at half of the laser scan values.

We learnt several useful lessons for future projects. First, it is beneficial to test on simple system. For example, testing with only 3 particles and no noise was very helpful because we can see exactly how the particles are moving based on Odometry. In general, testing with no noise to debug is a good idea. Secondly, if there is a bug in the code, isolate each function and test them seperately. We did this with the update particles with Odometry and we were able to determine that it was working correctly before moving on to other functions. 



