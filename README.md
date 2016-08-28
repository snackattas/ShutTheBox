# Shut The Box
This is a set of methods implementing the gameplay of the classic British pub game [Shut The Box](https://en.wikipedia.org/wiki/Shut_the_Box), created as project 8 of [Udacity's Full Stack Web Developer Nanodegree](https://www.udacity.com/course/full-stack-web-developer-nanodegree--nd004).  The entire game is implemented on the server side through Google's Cloud Endpoints.  Begin playing [here](https://apis-explorer.appspot.com/apis-explorer/?base=https://zattas-game.appspot.com/_ah/api#p/shut_the_box/v1/)

## Features
* The game is played on the client side using endpoints, and the state of the game is remembered through url keys, enabling the game to be extensible to javascript clients or iOS/Android platforms in the future.
* Each Shut The Box game is associated with a user, enabling various user statistics and reports to be created. 
* In addition to the standard Shut The Box gameplay with nine tiles and summing up the dice, users are able to configure games to contain twelve tiles (called "Full House") and/or multiplication of the dice instead of summing.
* Users receive email notifications for incomplete games of Shut The Box with turns more than 12 hours passed.  Users can of opt out of this email notification.
* A leaderboard features a list of users ranked by average score.

## Configuring a development environment
1. Download the github repository
2. Navigate to the top-level directory and boot up the app with the command `python lizardCatalog.py`. Press ctrl+c to shut down the app.
3. Open an internet browser and enter the url `localhost:8000`.

## Test Data
If you want to populate the lizard database with data automatically, use the [testData.py](https://github.com/snackattas/LizardApp/blob/master/testData.py)  script.  
Here's how to run the script:

1. First follow the setup steps to get the app up and running.
2. Create a user by logging into the web app.  Record the user id of your user.  It will be shown in the flash message.
3. In the top-level directory, run this command `python testData.py [user id]` subbing in "user id" with your user id.

## Technologies used
* [Google App Engine](https://cloud.google.com/appengine/)
* [Google Cloud Endpoints](https://cloud.google.com/endpoints/)
* Language: Python v2.7
* 3rd party package: [requests](http://docs.python-requests.org/en/master/)
* 3rd party package: [Mailgun](http://mailgun.com)

## JSON Endpoints
### [localhost:8000/lizard/JSON/](localhost:8000/lizard/JSON/)
    Displays all lizards
### localhost:8000/lizard/\[lizard_id\]/hobby/JSON/
    Displays all hobbies of a particular lizard
### localhost:8000/lizard/\[lizard_id\]/hobby/\[hobby_id\]/JSON/
    Displays only one hobby
## Atom Endpoints
### [localhost:8000/lizard.atom/](localhost:8000/lizard.atom/)
    Displays all lizards
### [localhost:8000/hobby.atom/](localhost:8000/hobby.atom/)
    Displays all hobbies
### [localhost:8000/all.atom/](localhost:8000/all.atom/)
    Displays all lizards and hobbies
###[localhost:8000/changes.atom/](localhost:8000/changes.atom/)
    Displays all content of the recent activity feed

## Screenshots
![Lizard Homepage](/../master/pkg/static/Lizard%20Homepage.JPG?raw=true "Lizard Homepage")
![Lizard's Hobby](/../master/pkg/static/Lizard%20Hobby.JPG?raw=true "Lizard's Hobbies")
