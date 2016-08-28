# Shut The Box
This is a set of methods implementing the gameplay of the classic British pub game [Shut The Box](https://en.wikipedia.org/wiki/Shut_the_Box), created as project 8 of Udacity's [Full Stack Web Developer Nanodegree](https://www.udacity.com/course/full-stack-web-developer-nanodegree--nd004).  The entire game is implemented on the server side through Google's Cloud Endpoints.  

Start playing [here](https://apis-explorer.appspot.com/apis-explorer/?base=https://zattas-game.appspot.com/_ah/api#p/shut_the_box/v1/)!

## Features
* Played on the client side using Google Cloud Endpoints. 
* Able to be used in javascript clients or iOS/Android platforms in the future.
* Each game is associated with a user, enabling various user statistics and reports to be created. 
* In addition to the standard Shut The Box gameplay with nine tiles and dice addition, users are able to configure games to contain twelve tiles (called "Full House") and/or multiplication of the dice.
* Users receive email notifications for incomplete games.
* A leaderboard features a list of users ranked by average score and average number of turns.

## Rules of Shut The Box
The game uses tiles numbered 1 to 9.  The player rolls two dice and flips any combination of tiles that match the sum of the roll. If every tile higher than 6 is flipped, the player then rolls only one dice.  The player keeps rolling and flipping until they can't match their roll with the remaining tiles.  The total of thet tiles left unflipped are then totaled, and that is the score.  Lower scores are therefore considered better, as they are the result of flipping more tiles.

In this version of Shut The Box, the user has the ability to play with tiles numbered 1 to 12.  They are also able to choose to flip a combination of tiles that match the product of the dice roll, instead of the sum.

## How to Play
1. Create a user by calling create_user. 
2. Create a game by calling new_game with your username and the dice operation/number of tiles to play with. Record the urlsafe_key that is returned.
3. Call turn with the urlsafe_key. Your roll will be returned.
4. Call turn again with the urlsafe_key and with flip_tiles as the combination of tiles that match the sum (or product) of the roll.
5. Repeat step 4 until the game is over.
6. Call new_game and play again!

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
Plays one turn of Shut The Box.  To play Shut The Box, first call turn with only a urlsafe_key and flip tiles null.  It returns a roll and a full set of tiles.  Each subsequent call of turn must include both a urlsafe_key and flip_tiles, and turn will determine the validity of flip_tiles and compute the next roll.  The goal is to flip all the tiles and get the lowest score possible.
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
Searches for games matching the passed in search criteria and returns basic information about them. Will return an error if both games in progress and finished games are True.
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

### get_user_stats
Returns user statistics for a particular user.  The statistics are games completed, total score, total turns, average score, and average turns.  Able to filter by dice operation and/or number of dice.
* Args
  * username (string, req): A unique username.
  * number_of_tiles (enum, opt): Filters games by number of tiles.
  * dice_operation (enum, opt): Filters games by dice operation.
* Returns
  * games_completed: Number of games completed.
  * total_score: Total score of completed games.
  * total_turns: Total number of turns for completed games.
  * average_score: Average score from completed games, rounded to 3 decimal places.
  * average_turns: Average turns from completed games, rounded to 3 decimal places.
  * message: Helpful error message.
* Raises: NotFoundException

### get_high_scores
Returns a list of games in order of high score, with details about the game.  In Shut The Box, lower scores are better, so a list of high scores is a list of the scores from lowest to highest.  In the case of a tie, order is determined by which game finished first.
The list of high scores is able to be filtered by dice operation and/or number of tiles.
* Args
  * number_of_tiles (enum, opt): Filters games by number of tiles.
  * dice_operation (enum, opt): Filters games by dice operation.
  * number_of_results (int, opt): Default is 20.  Number of high scores to return.
* Returns
  * high_scores: List of games ordered by high scores.  Each game is made up of the parameters below:
    * score: The final score.
    * username: The user who played this game.
    * number_of_tiles: Number of tiles for this game.
    * dice_operation: Dice operation for this game.
    * timestamp: The date and time when the game was completed.
  * message: Helpful error message
* Raises: BadArgumentError

### get_leaderboard
List of ranked users.  Users are ranked by average score from low to high, and in the case of a tie in average score, the rank is determined by lowest average turns.  Users are only able to be ranked if they have completed 5 or more games.  The leaderboard is able to be filtered by games with certain dice operation and/or number of tiles.
* Args
  * number_of_tiles (enum, opt): Filters leaderboard by number of tiles.
  * dice_operation (enum, opt): Filters leaderboard by dice operation.
  * username (str, opt):  If specified returns rank of only that user.
* Returns
  * ranked_users: List of users ordered by rank.  Each user is made up of the parameters below.
    * username: A unique username.
    * total_score: Total score of completed games.
    * total_turns: Total number of turns for completed games.
    * average_score: Average score from completed games, rounded to 3 decimal places.
    * average_turns: Average turns from completed games, rounded to 3 decimal places.
    * games_completed: Number of games completed.
    * rank: Rank of the user.
  * message: Helpful error message
* Raises: NotFoundException

### get_game_history
Returns the history of moves for the game passed in, allowing game progression to be viewed move by move. Similar to chess's [PGN](https://en.wikipedia.org/wiki/Portable_Game_Notation)
* Args
  * urlsafe_key (string, req): The state token for a game of Shut The Box.
* Returns
  * turns: List of turns for a specific game.  Each turn is made up of the parameters below.
    * turn: The turn number. Turn 0 is the first roll, and does not have tiles played.  Each subsequent turn has both a roll and tiles played.
    * roll: The dice roll for this turn.
    * tiles_played: The tiles flipped this turn.
    * score: A running total of the active tiles in play.
    * game_over: If True, game ended with this turn.
* Raises: BadRequestException, ValueError
