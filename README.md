# Shut The Box
This is a set of methods implementing the gameplay of the classic British pub game [Shut The Box](https://en.wikipedia.org/wiki/Shut_the_Box), created as project 8 of Udacity's [Full Stack Web Developer Nanodegree](https://www.udacity.com/course/full-stack-web-developer-nanodegree--nd004).  The entire game is implemented on the server side through Google's Cloud Endpoints.  

Start playing [here](https://apis-explorer.appspot.com/apis-explorer/?base=https://zattas-game.appspot.com/_ah/api#p/shut_the_box/v1/)!

## Features
* Played on the client side using Google Cloud Endpoints. The game state is remembered through url keys, enabling the game to be extensible to javascript clients or iOS/Android platforms in the future.
* Each game is associated with a user, enabling various user statistics and reports to be created. 
* In addition to the standard Shut The Box gameplay with nine tiles and dice addition, users are able to configure games to contain twelve tiles (called "Full House") and/or multiplication of the dice instead of summing.
* Users receive email notifications for incomplete games with turns more than 12 hours passed.
* A leaderboard features a list of users ranked by average score and average number of turns.

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

## Cloud Endpoints
###create_user
Creates a user
* Args
  * username (string, req): A unique username without leading spaces.
  * email (string, opt): A unique and valid email.  Email is validated using MAILGUN email validation API.
  * email_notification (boolean, opt): True by default.  If true, user will receive email notifications of outstanding active games.
* Returns
  * message: A message confirming user was created, or an error
#### registerPlayer(player_name, tournament_id)
Adds a player to a specific tournament. The database assigns a unique ID number to the player. Different players may have the same names but will receive different ID numbers.
#### countPlayers(tournament_id)
Returns the number of players currently registered in a specific tournament.
#### deleteTournament(tournament_id)
Removes the specified tournament.  All the tournament's players, matches, and records are also removed.
#### deleteMatches(tournament_id)
Removes all the match records from the database for a specific tournament.
#### deletePlayers(tournament_id)
Clear out all the player records from the database for a specific tournament.
#### reportMatch(winner, loser, tie=None, bye=None, tournament_id)
Records the outcome of a single match between two players in the same tournament.  Also able to record byes for a single player.
#### playerStandings(tournament_id)
Returns a list of (id, name, wins, matches) for each player in the tournament.  Player standing is calculated by a score assigned to each player.  Players are sorted from highest to lowest scoring.
#### swissPairings(tournament_id)
Returns a list of pairs of players for the next round of a match.  Each player is paired with the adjacent player in the standings.  If there are an odd number of players, the last player returned (the one with the lowest standing) will be the one which receives a bye.
