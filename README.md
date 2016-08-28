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
### create_user
Creates a user.
* Args
  * username (string, req): A unique username without leading spaces.
  * email (string, opt): A unique and valid email.  Email is validated using MAILGUN email validation API.
  * email_notification (boolean, opt): True by default.  If True, user will receive email notifications of outstanding active games that haven't been played in the last 12 hours.
* Returns
  * message: A message confirming user was created, or an error
* Raises: ConflictException

### set_email_notification_preference
Allows a user to change their email notification preference.
* Args
  * username (string, req): A unique username.
  * email_notification (boolean, req): If True, user will receive email notifications of outstanding active games that haven't been played in the last 12 hours.  If False, users will stop receiving these notifications.
* Returns
  * message: A message confirming email notification preference, or an error.
* Raises: NotFoundException

### new_game
Creates a new game and returns the game's urlsafe key.
* Args
  * username (string, req): A unique username.
  * number_of_tiles (enum, req): Number of tiles to play Shut The Box with.
  * dice_operation (enum, req): Determines if the number to aim for with the flipped tiles is the sum of the dice roll or the product.
* Returns
  * username: User's username.
  * number_of_tiles: Number of tiles to play Shut The Box with.
  * dice_operation: Determines if the number to aim for with the flipped tiles is the sum of the dice roll or the product.
  * urlsafe_key: This serves as the state token for a game of Shut The Box.
  * message: A helpful message or an error message.
* Raises: NotFoundException, ConflictException

### turn
Plays one turn of Shut The Box.  To play Shut The Box, first call turn() with only a urlsafe_key and flip tiles null.  It returns a roll and a full set of tiles.  Each subsequent call of turn() must include both a urlsafe_key and flip_tiles, and turn() will determine the validity of flip_tiles and compute the next roll.  The goal is to flip all the tiles and get the lowest score possible.
* Args
  * urlsafe_key (string, req): The state token for a game of Shut The Box.
  * flip_tiles (list of non-negative integers, null/req): For the first turn, leave this parameter null.  On subsequent calls, flip_tiles are the integers to be flipped in response to the roll.
* Returns
  * urlsafe_key: The state token for a game of Shut The Box.
  * roll: A list of two integers, each between 1-6, if there are active tiles above 7 in play.  If all tiles above 7 are inactive only one integer is returned.
  * active_tiles: The newly computed active_tiles left after the roll has been played.
  * score: A running score of the active_tiles in play. 
  * game_over: If True, game is over.
  * message: A helpful message or an error message.
* Raises: BadRequestException, ValueError

### cancel_game
Cancels a Game entity and its children Turn entities.  User can only cancel games in progress.
* Args
  * urlsafe_key (string, req): The state token for a game of Shut The Box.
* Returns
  * cancelled: True if the game entity and Turn entities are deleted from the datastore; False if the game entity in question is completed.
  * error: Helpful error message.
* Raises: BadRequestException, ValueError

### find_games
Searches for games matching the passed in search criteria and returns basic information about them. Will return an error if both games_in_progress and finished_games are True.
* Args
  * games_in_progress (boolean, opt): False by default. If True, filters by games in progress. 
  * finished_games (boolean, opt): False by default. If True, filters by finished games. 
  * number_of_tiles (enum, opt): Filters games by number of tiles.
  * dice_operation (enum, opt): Filters games by dice operation.
  * username (string, opt): Filters by username.
* Returns
  * games: A list of games. Each game is made up of the parameters below.
   * urlsafe_key: The state token for this game of Shut The Box.
   * number_of_tiles: Number of tiles for this game.
   * dice_operation: Dice operation for this game.
   * game_over: If true, this game is over.
   * turns_played: Number of turns played for this game.
* Raises: NotFoundException, BadRequestException
