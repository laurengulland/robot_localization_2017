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

One thing we would have liked to work on to take this one step further is implementing cluster tracking. By accounting for the possibility of the particles dividing into clusters (like you see on the map below), we would have been able to adjust for situations like these without just taking the mean of the top weighted particles to find robot pose.
![Clustering Problems](https://github.com/laurengulland/robot_localization_2017/blob/master/my_localizer/videos/particle_filter_cluster.png)

## Adapting to Inaccurate Starting Positions
One additional feature that we were interested in is the ability to recover from an inaccurate starting position. In the gif below, you can see that despite being given a very incorrect heading and a mildly incorrect x-y position, the model recovers well in about 5 seconds by scattering particles much more randomly until they start returning higher confidence in their placement, and then honing down to a more reasonable amount of positional noise when the model is more confident it's in the right place.
![Recovering from an inaccurate initial position](https://github.com/laurengulland/robot_localization_2017/blob/master/my_localizer/videos/ac109_1_bad_initial.gif "animation")

# Process, Lessons, and Improvements

One challenge we ran into along the way was making sure our static and dynamic coordinate transforms were correct. This should have been a small thing, but definitely tripped us up because we weren't actively looking for it or thinking about it when writing our code initially, so we didn't get it quite right. Thankfully, with a bit of help, we got it working really well, but we should have been more aware of all the things we would have to be juggling when starting to dive into code development. 

In addition to the improvement of cluster tracking mentioned above, we would have liked to dive more into getting our own map working. We created our own map and bag file to throw a different set of data at our model to see how it responds, but unfortunately couldn't get that working. We think that just requires some more debugging and understanding of ROSservices, which will hopefully be something we can learn in the future!

_Lessons Learned?_
