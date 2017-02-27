# Project Overview
This project was completed by Judy Xu and Lauren Gulland for Paul Ruvolo's Computational Robotics class at Olin College of Engineering in Spring 2017. The goal of this project was to build fluency with ROS, understand particle filtering and robot localization, and learn more about building, writing, and understanding algorithms for robotics. See more info about this project on the course website [here](https://sites.google.com/site/comprobo17/projects/robot-localization).

This writeup is intended to capture our work, and is broken down into the following sections:
  - [Project Implementation](#project-implementation)
    - [Particle Resampling](#particle-resampling)
    - [Determining Robot Pose from Particles](#determining-robot-pose-from-particles)
    - [Updating Particles with Laser Scan Data](#updating-particles-with-laser)
    - [Updating Particles with Odometry](#updating-particles-with-odometry)
    - [Adapting to Inaccurate Starting Positions](#adapting-to-inaccurate-starting-positions)
  - [Project Reflection](#project-reflection)
    - [Challenges](#challenges)
    - [Improvements](#improvements)
    - [Lessons Learned](#lessons-learned)

# Project Implementation 
We implemented our particle filter with the following segments: 
  - The particle filter initializes a cloud of particles in a random position, and updates it when the user adds a Robot 2D Pose Estimate in RViz. (The initial robot pose is estimated from this particle cloud as explained in a later step.)
  - As the robot drives, the particles each update their positions with the odometry readings from the actual robot's readings.
  - Each particle is tested for what its laser scan values would be if the robot were in that position on the map, and returns a confidence value for how likely it is that the robot is in that position given the real and theoretical particle laser scan data. Based on the confidence of each particle's position, it is assigned a weight, which is then normalized across the entire cloud of particles.
  - Based on the confidences of each particle in the cloud, we then resample our particles to keep some and add more noise to the rest of our guesses.

Each of these component pieces very closely tie together, and the entire algorithm cycles through each part very quickly to update everything in almost real-time, with a slight delay. More detail on each of these can be found in the subsequent subsections.
  
You can see our model's performance here:
![Working Base Model](https://github.com/laurengulland/robot_localization_2017/blob/master/my_localizer/videos/ac109_1_good_initial.gif)

## Particle Resampling 
One interesting decision we made while designing our particle filter was how to resample our particles in response to calculating their respective weights. Obvious answers to this include keeping only the particles in the most common position of the pack and eliminating outliers, or semi-randomly choosing to keep particles and letting their weights determine their likelihood to be kept or eliminated. We decided to combine these methods early on in our code design, and created a resampling mechanism that automatically kept a number of the top-weighted particles and then semi-randomly (accounting for weights) chose from the rest to fill a certain quota of particles we would keep. We then added varying amounts of noise to this core set of kept particles to backfill the rest of our cloud, which gave us the continued variation to help in recovering from imperfect weighting and updating.

## Determining Robot Pose from Particles
Currently, we have two options we can choose from manually to determine the robot pose based on our particle cloud: mean-driven and mode-driven. 

Mean-driven pose updating averages the positions of all the particles together to determine the average position of the cloud. This works because of the way that we add noise to our particle cloud; because the noise is a gaussian distribution aroound the most confident particles, the natural center of the cloud will be the most likely place for the robot to be located.

Mode-driven pose updating takes only the position of the particle with the heaviest weighting at that moment. This can be more unreliable because it relies on a smaller number of particles, so we tend to use mean-driven pose updating unless a situation calls for mode-driven. Such an example of a situation that would react better to mode-driven pose updating would be if a particular map is conducive to multiple clusters forming in different places -- mode-driven will give you a result from within one of the clusters, but mean-driven may give you a result between two clusters where there aren't any particles.

One thing we would have liked to work on to take this one step further is implementing cluster tracking. By accounting for the possibility of the particles dividing into clusters (like you see on the map below), we would have been able to adjust for situations like these without just taking the mean of the top weighted particles to find robot pose.
![Clustering Problems](https://github.com/laurengulland/robot_localization_2017/blob/master/my_localizer/videos/particle_filter_cluster.png)

## Updating particles with laser
We chose a simple method of updating the weights of the particles with laser. First, we got the closest distance to an obstacle in the map from Occupancy field for each measurement of each particle. Based on this closest distance, we calculated the probability using a normal distribution with a very small standard deviation. We then added the cube of each measurement probablity up for each particle and that is their weight. We used the cube based on the ROS particle filter model. One important decision we made is to use all the laser measurements (360 of them). This really improved the accuracy of our particle filter, and we compensated for the increase in code running time by decreasing the number of particles to 100. For a complicated environment, 100 particles might still be too much, so it needs to be further decreased. We also ignored NaN values and invalid values of the laser scan.

## Updating particles with Odometry 
Updating the particle position using the robot's odometry readings is fairly straightforward. As soon as the robot has moved a certain distance in linear or rotational position, we calculate the pose change relative to the robot's current pose, and apply this change to each of the particles' poses. 

Once each particle has been updated with the robot's odom readings, we add noise of varying degrees to each particle. This step is crucial, because it allows us to correct for incorrect odom readings due to slippage, drift, and other problems that make odometry imperfect. This is a similar kind of noise to when we resample our particles, but specifically tuned to account for odometry inaccuracies more efficiently.

## Adapting to Inaccurate Starting Positions
One additional feature that we were interested in is the ability to recover from an inaccurate starting position. In the gif below, you can see that despite being given a very incorrect heading and a mildly incorrect x-y position, the model recovers well in about 5 seconds by scattering particles much more randomly until they start returning higher confidence in their placement, and then honing down to a more reasonable amount of positional noise when the model is more confident it's in the right place.
![Recovering from an inaccurate initial position](https://github.com/laurengulland/robot_localization_2017/blob/master/my_localizer/videos/ac109_1_badinitial_cropped.gif "animation")

# Project Reflection

## Challenges

One challenge we ran into along the way was making sure our static and dynamic coordinate transforms were correct. In the beginning in Update particles with Odom we didn't use the relative movement with respect to the robot's pose to update the particles, and our particles just moved in different directions from the robot. This should have been a small thing, but definitely tripped us up because we weren't actively looking for it or thinking about it when writing our code initially, so we didn't get it quite right. Thankfully, with a bit of help, we got it working really well, but we should have been more aware of all the things we would have to be juggling when starting to dive into code development. 

Another challenge we faced was aliasing. In resample particles, we tripled a particle list and forgot to do a deep copy. This resulted in modifying the same particle 3 times in normalizing particles and we kept getting weights that are huge. We solved this problem by using deep copy with a for loop. 

Lastly, we had some difficulties tuning our particle filter. We started by tuning each noise parameter but adding noise just seemed to worsen the performance. Then we tried resampling to fewer particles and thar helped a little. Finally when we were about to give up in frustration we chaged from using each second laser scan measurement to using all of them. Suddenly our particle filter worked really well. After this, increasing noise improved the ability to recover from deviations.

## Improvements
In addition to the improvement of cluster tracking mentioned above, we would have liked to dive more into getting our own map working. We created our own map and bag file to throw a different set of data at our model to see how it responds, but unfortunately it doesn't have a map_pose so we can not determine the performance of our particle filter on it. However, our particle filter did create a TimeOut Error when run on our own map. I think this is because in our own map all 360 degrees have a valid laser scan and that takes too much time to process. Thus, in the future it might be good to dynamically set the number of particles to reduce runtime. For example, if it takes too long to update with laser, we either decrease the number of particles or look at half of the laser scan values.

## Lessons Learned
We learned several useful lessons for future projects:

First, it is beneficial to test on a simple system. For example, testing with only 3 particles and no noise was very helpful because we can see exactly how the particles are moving based on Odometry. In general, testing with no noise to debug was a good idea. 

Secondly, if there is a bug in the code, isolate each function and test them seperately. We did this with the update particles with odometry and we were able to determine that it was working correctly before moving on to other functions, which really helped us debug and is very applicable in the future.

Finally, we think we struck a good balance between pair programming and individualized tasks throughout this project. When making large decisions about things like how functions would interact, we obviously worked very closely together, but then split up implementation more in order to parallelize the work we were doing. We also tended to work on the project together even if the parts we were doing were separate, which helped with clarifying function interaction and code direction, answering each others' technical quesitons, and also making sure we were on the same page. 
