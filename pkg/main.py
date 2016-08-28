"""main.py - This file creates and configures the Google Cloud Endpoints
for the ShutTheBox game, and contains part of the game logic and statistical
methods."""

import endpoints
from protorpc import remote, messages, message_types
from google.appengine.ext import ndb
from google.appengine.api import memcache

import logging
from models import User, Game, Turn
# Forms for doing the CRUD on the database
from models import CreateUserRequestForm, CreateUserResultForm
from models import EmailNotificationRequestForm, EmailNotificationResulForm
from models import NewGameRequestForm, NewGameResultForm
from models import TurnRequestForm, TurnResultForm
from models import CancelResultForm
# These next forms just read data
from models import FindGamesRequestForm, TotalFindGamesResultForm
from models import UserStatsRequestForm, UserStatsResultForm
from models import HighScoresRequestForm, TotalHighScoresResultForm
from models import LeaderboardRequestForm, UserLeaderboardResultForm, \
    TotalLeaderboardResultForm
from models import AllTurnsReportResultForm

from utils import get_by_urlsafe

from collections import namedtuple
from operator import attrgetter
import pickle

# # ONLY UNCOMMENT/IMPORT THE MODULES BELOW IF USING THE test_method
# from models import InsertOrDeleteDataRequestForm, InsertOrDeleteDataResultForm
# INSERT_OR_DELETE_REQUEST = endpoints.ResourceContainer(
#     InsertOrDeleteDataRequestForm)
# import json
# import requests as outside_requests
# import random

CREATE_USER_REQUEST = endpoints.ResourceContainer(CreateUserRequestForm)
EMAIL_NOTIFICATION_REQUEST = endpoints.ResourceContainer(
    EmailNotificationRequestForm)
NEW_GAME_REQUEST = endpoints.ResourceContainer(NewGameRequestForm)
# Adding urlsafe_key like this makes it a required parameter and passes it as
# a path parameter in the URL
TURN_REQUEST = endpoints.ResourceContainer(TurnRequestForm,
    urlsafe_key=messages.StringField(1))
URLSAFE_KEY_REQUEST = endpoints.ResourceContainer(
    urlsafe_key=messages.StringField(1))

FIND_GAMES_REQUEST = endpoints.ResourceContainer(FindGamesRequestForm)
USER_STATS_REQUEST = endpoints.ResourceContainer(UserStatsRequestForm)
HIGH_SCORES_REQUEST = endpoints.ResourceContainer(HighScoresRequestForm)
LEADERBOARD_REQUEST = endpoints.ResourceContainer(LeaderboardRequestForm)


@endpoints.api(name='shut_the_box', version='v1')
class ShutTheBoxApi(remote.Service):
    """A set of methods implementing the gameplay of the classic British pub
    game Shut The Box.  The entire game is implemented on the server-side
    through Google's Cloud Endpoints.  The state of a game is remembered by
    passing an individual game's entity key to the client, serving as a state
    token."""

    # First 4 APIs are functional and actually do things
    @endpoints.method(request_message=CREATE_USER_REQUEST,
                      response_message=CreateUserResultForm,
                      path='create_user',
                      name='create_user',
                      http_method='POST')
    def create_user(self, request):
        """Creates a User.

        :param username (req): A unique username without leading spaces.
        :type username: string
        :param email (opt): A unique and valid email.  Email is validated using
        MAILGUN email validation API.
        :type email: string
        :param email_notification (opt): True by default.  If True, user will
        receive email notifications of outstanding active games.
        :type email_notification: boolean

        :returns message: A message confirming user was created, or an error
        message.
        :rtype message: string

        :raises: ConflictException"""

        # Some format checking
        if not request.username:
            raise endpoints.ConflictException(
                    'User name cannot be null')
        if len(request.username) != len(request.username.lstrip(' ')):
            raise endpoints.ConflictException(
                    'User name can not have leading spaces')
        if request.username.isspace():
            raise endpoints.ConflictException(
                    'User name cannot be null')

        # Checking for duplicate entries
        if User.query(User.username == request.username).get():
            raise endpoints.ConflictException(
                'A user with the name {} already exists!'.
                format(request.username))

        # Only check if email is valid if there is an email to check
        if request.email:
            if User.query(User.email == request.email).get():
                raise endpoints.ConflictException(
                    'A user with the email {} already exists!'.
                    format(request.email))
            # Checking if the email is valid via MAILGUN APIs
            if not User.is_email_valid(request.email):
                return CreateUserResultForm(
                    message="Email address invalid! User is not created.")
            # All is good, saving User object
            user = User(
                username=request.username,
                email=request.email,
                email_notification=request.email_notification)
            user.put()
        else:
            user = User(username=request.username)
            user.put()
        return CreateUserResultForm(message='User {} created!'.
                             format(request.username))


    @endpoints.method(request_message=EMAIL_NOTIFICATION_REQUEST,
                      response_message=EmailNotificationResulForm,
                      path='email_notification',
                      name='email_notification',
                      http_method='POST')
    def set_email_notification_preference(self, request):
        """Allows a user to change their email notification preference.

        :param username (req): A unique username without leading spaces.
        :type username: string
        :param email_notification (req): If True, user will receive email
        notifications of outstanding active games that haven't been played in
        the last 12 hours.  If False, users will stop receiving these
        notifications.
        :type email_notifications: boolean

        :returns message: A message confirming email notification preference,
        or an error.
        :rtype message: string"""

        user = User.query(User.username == request.username).get()
        if not user:
            raise endpoints.NotFoundException(
                    'A user with the name {} does not exist!'.\
                    format(request.username))
        user.email_notification = request.email_notification
        user.put()
        return EmailNotificationResulForm(message="Email notification"\
            "preferences set to {}".format(request.email_notification))


    @endpoints.method(request_message=NEW_GAME_REQUEST,
                      response_message=NewGameResultForm,
                      path='new_game',
                      name='new_game',
                      http_method='POST')
    def new_game(self, request):
        """Creates a new game and returns the game's urlsafe key.

        :param username (req): A unique username.
        :type username: string
        :param number_of_tiles (req): Number of tiles to play Shut The Box with.
        :type number_of_tiles: enum-{NINE, TWELVE}
        :param dice_operation (req): When two dice are rolled in a turn,
        this determines if the number to aim for with the flipped tiles is the
        sum of the dice roll or the product.
        :type dice_operation: enum-{ADDITION, MULTIPLICATION}

        :returns username: User's username.
        :rtype username: string
        :returns number_of_tiles: Number of tiles to play Shut The Box with.
        :rtype number_of_tiles: enum-{NINE, TWELVE}
        :returns dice_operation: When two dice are rolled in a turn,
        this determines if the number to aim for with the flipped tiles is the
        sum of the dice roll or the product.
        :rtype dice_operation: enum-{ADDITION, MULTIPLICATION}
        :returns urlsafe_key: This serves as the state token for a game of Shut
        The Box.
        :rtype urlsafe-key: string
        :returns message: A helpful message or an error message.
        :rtype message: string

        :raises: NotFoundException, ConflictException"""

        user = User.query(User.username == request.username).get()
        if not user:
            raise endpoints.NotFoundException(
                    'A user with the name {} does not exist!'.\
                    format(request.username))
        if not request.number_of_tiles or not request.dice_operation:
            raise endpoints.ConflictException(
                'User must specify the number of tiles and the dice operation')
        game = Game.new_game(user.key, request.number_of_tiles.number,
                            request.dice_operation.name)
        return game.to_new_game_result_form("Good luck playing Shut The"\
                                            "Box,{}!".format(user.username))


    @endpoints.method(request_message=TURN_REQUEST,
                      response_message=TurnResultForm,
                      path='game/{urlsafe_key}',
                      name='turn',
                      http_method='PUT')
    def turn(self, request):
        """Plays one turn of Shut The Box.

        To play Shut The Box, first call turn() with only a urlsafe_key and flip
        tiles null.  It returns a roll and a full set of tiles.
        Each subsequent call of turn() must include both a urlsafe_key and
        flip_tiles, and turn() will determine the validity of flip_tiles and
        compute the next roll.  The goal is to flip all the tiles and get the
        lowest score possible.

        :param urlsafe_key (req): The state token for a game of Shut The Box.
        :type urlsafe_key: string
        :param flip_tiles (opt): Leave this parameter null for the first call of
         turn().  On subsequent calls, flip_tiles are the integers to be
         flipped in response to the roll.
        :type flip_tiles: list of non-negative integers

        :returns urlsafe_key: The same urlsafe_key passed in.
        :rtype urlsafe_key: string
        :returns roll: A list of two integers, each between 1-6, if there are
        active tiles above 7 in play.  If all tiles above 7 are inactive only
        one integer is returned.
        :rtype roll: list of non-negative integers
        :returns active_tiles: The newly computed active_tiles left after the
        roll has been played.
        :rtype active_tiles: A list of non-negative integers
        :returns valid_move: True if flip_tiles played are valid, False if they
        are not valid.
        :rtype valid_move: boolean
        :returns score: A running score of the active_tiles in play.
        :rtype score: non-negative integer
        :returns game_over: If True, game is over.
        :rtype game_over: boolean
        :returns message: A helpful message or an error message.
        :rtype message: string

        :raises: BadRequestException, ValueError"""

        # First make sure the game's key is real/not game over status
        game = get_by_urlsafe(request.urlsafe_key, Game)
        if game.game_over:
            form = TurnResultForm()
            form.urlsafe_key = request.urlsafe_key
            form.valid_move = False
            form.game_over = True
            form.message = "This game is already over.  Play again by calling "\
                           "new_game()!"
            return form
        # If it's a real game, get the most recent turn
        MEMCACHE_KEY = game.key.urlsafe()
        recent_turn = game.most_recent_turn()
        if not recent_turn:
            # If recent_turn is null, this is the first roll!
            turn = Turn.first_turn(game)
            if not memcache.add(key=MEMCACHE_KEY, value=pickle.dumps(turn),
                time=360):
                logging.warning("Memcache addition failed!")
            return turn.to_turn_result_form(
                urlsafe_key=game.key.urlsafe(),
                valid_move=True,
                message="Call turn() again to play your roll")
        # If it's not a user's first turn, user must pass in flip_tiles
        if not request.flip_tiles:
            return recent_turn.to_turn_result_form(
                urlsafe_key=game.key.urlsafe(),
                valid_move=False,
                message="User must pass in values to flip_tiles!")
        # Check if it's a valid flip
        error = recent_turn.invalid_flip(request.flip_tiles,
                                         game.dice_operation)
        if error:
            return recent_turn.to_turn_result_form(
                urlsafe_key=game.key.urlsafe(),
                valid_move=False,
                message=error)
        # Since it's a valid flip, end the last turn
        recent_turn.end_turn()
        # Create a new turn
        new_turn = recent_turn.new_turn(game, request.flip_tiles)
        # If the new turn does not have any active tiles, it's a perfect score
        # and the game's over
        if not new_turn.active_tiles:
            new_turn.end_game(game)
            return new_turn.to_turn_result_form(
                urlsafe_key=game.key.urlsafe(),
                valid_move=True,
                message="Game over! Perfect score! Call new_game() to play again!")
        # Check if the roll from the new turn ends the game
        game_over = new_turn.is_game_over(game)
        if game_over:
            new_turn.end_game(game)
            return new_turn.to_turn_result_form(
                urlsafe_key=game.key.urlsafe(),
                valid_move=True,
                message="Game over! Call new_game() to play again!")
        # If the code's fallen through to here, the roll is valid.  Add newest turn to memcache
        if not memcache.replace(key=MEMCACHE_KEY, value=pickle.dumps(new_turn),
            time=360):
            logging.warning("Memcache logging failed!")
        return new_turn.to_turn_result_form(
            urlsafe_key=game.key.urlsafe(),
            valid_move=True,
            message="Call turn() again to play your roll")


    @endpoints.method(request_message=URLSAFE_KEY_REQUEST,
                      response_message=CancelResultForm,
                      path='cancel_game/{urlsafe_key}',
                      name='cancel_game',
                      http_method='DELETE')
    def cancel_game(self, request):
        """Cancels a Game entity and its children Turn entities.  User can
        only cancel games in progress.  This API operates under the assumpion
        that it's better to just cancel games outright instead of somehow
        marking them as deleted in the database.

        :param urlsafe_key (req): The state token for a game of Shut The Box.
        :type urlsafe_key: string

        :returns cancelled: True if the game entity and Turn entities are
        deleted from the datastore; False if the game entity in question is
        completed.
        :rtype cancelled: boolean
        :returns error: Helpful error message.
        :rtype error: string

        :raises: BadRequestException, ValueError"""

        game = get_by_urlsafe(request.urlsafe_key, Game)
        if game.game_over:
            return CancelResultForm(
                cancelled=False,
                error="Can't cancel games that are already completed.")

        # This deletes both the parent game and the children turns
        ndb.delete_multi(ndb.Query(ancestor=game.key).iter(keys_only=True))
        return CancelResultForm(cancelled=True)


    # The next APIs are statistics, game state information, and leaderboards
    # They don't create, update, or delete the database, they just read from
    # it

    # The rubric calls for a method get_user_games, but I expanded this API to
    # have that functionality and more
    @endpoints.method(request_message=FIND_GAMES_REQUEST,
                      response_message=TotalFindGamesResultForm,
                      path='find_games',
                      name='find_games',
                      http_method='POST')
    def find_games(self, request):
        """Searches for games matching the passed in search criteria and
        returns basic information about them.

        Will return an error if both games_in_progress and finished_games are
        True.

        :param games_in_progress (opt): False by default. If True, filters by
        games in progress.
        :type games_in_progress: boolean
        :param finished_games (opt): False by default. If True, filters by
        finished games.
        :type finished_games: boolean
        :param number_of_tiles (opt): Filters games by number of tiles.
        :type number_of_tiles: enum-{NINE, TWELVE}
        :param dice_operation (opt): Filters games by dice operation.
        :type dice_operation: enum-{ADDITION, MULTIPLICATION}
        :param username (opt): Filters by username.
        :type username: string

        :returns games: A list of games. Each game is made up of the parameters
        below.
        :rtype games: list
        :returns urlsafe_key: The state token for this game of Shut The Box.
        :rtype urlsafe_key: string
        :returns number_of_tiles: Number of tiles for this game.
        :rtype number_of_tiles: enum-{NINE, TWELVE}
        :returns dice_operation: Dice operation for this game.
        :rtype dice_operation: enum-{ADDITION, MULTIPLICATION}
        :returns game_over: If True, this game is over.
        :rtype game_over: boolean
        :returns turns_played: Number of turns played for this game.
        :rtype turns_played: integer

        :raises: NotFoundException, BadRequestException"""

        # if username is passed in, look for only their games
        if request.username:
            user = User.query(User.username == request.username).get()
            if not user:
                raise endpoints.NotFoundException(
                        'A user with the name {} does not exist!'.\
                        format(request.username))
            games_query = Game.query(ancestor=user.key)
        else:
            games_query = Game.query()

        if request.games_in_progress == True \
            and request.finished_games == True:
            raise endpoints.BadRequestException("games_report can't be called "
                "with both parameters games_in_progress and finished_games "
                "True")

        if request.games_in_progress:
            games_query = games_query.filter(Game.game_over == False)
        if request.finished_games:
            games_query = games_query.filter(Game.game_over == True)
        if request.number_of_tiles:
            games_query = games_query.filter(
                Game.number_of_tiles == request.number_of_tiles.number)
        if request.dice_operation:
            games_query = games_query.filter(
                Game.dice_operation == request.dice_operation.name)

        # Return the most recent games first
        games_query = games_query.order(-Game.timestamp)
        games = games_query.fetch()

        return TotalFindGamesResultForm(
            games=[game.to_find_games_result_form() for game in games])


    @endpoints.method(request_message=USER_STATS_REQUEST,
                      response_message=UserStatsResultForm,
                      path='user_stats',
                      name='user_stats',
                      http_method='POST')
    def get_user_stats(self, request):
        """Returns user statistics for a particular user.

        The statistics are completed games, total score, total turns, average
        score, and average turns.  Able to filter by dice operation and number
        of dice.

        :param username (req): A unique username.
        :type username: string
        :param number_of_tiles (opt): If specified, filters to return games
        with the specified number_of_tiles.
        :type number_of_tiles: enum-{NINE, TWELVE}
        :param dice_operation (opt): If specified, filters to return games
        with the specified dice_operation.
        :type dice_operation: enum-{ADDITION, MULTIPLICATION}

        :returns games_completed: Number of games completed.
        :rtype games_completed: integer
        :returns total_score: Total score of completed games.
        :rtype total_score: integer
        :returns total_turns: Total number of turns for completed games.
        :returns average_score: Average score from completed games, rounded
        to 3 decimal places.
        :rtype average_score: float
        :returns average_turns: Average turns fromcompleted games, rounded
        to 3 decimal places.
        :rtype average_turns: float
        :returns message: Helpful error message.
        :rtype message: string

        :raises: NotFoundException"""
        # TODO: For the life of me, I could not figure out how to make this
        # method into a GET request with multiple query parameters (username,
        # number_of_dice, dice_operation).  I was able to figure out how to
        # do it with one parameter, but not multiple.  And the google
        # tutorial only features GETs with 1 parameter.
        # https://github.com/GoogleCloudPlatform/python-docs-samples/blob
        # /master/appengine/standard/endpoints/backend/main.py

        user = User.query(User.username == request.username).get()
        if not user:
            raise endpoints.NotFoundException(
                    'A user with the name {} does not exist!'.\
                    format(request.username))

        games_query = Game.query(ancestor=user.key)
        # Only return games that have a status of game_over
        games_query = games_query.filter(Game.game_over == True)

        # Optional filters
        if request.number_of_tiles:
            games_query = games_query.filter(
                Game.number_of_tiles == request.number_of_tiles.number)
        if request.dice_operation:
            games_query = games_query.filter(
                Game.dice_operation == request.dice_operation.name)

        games = games_query.fetch()
        if not games:
            return UserStatsResultForm(message="No games found!")

        (games_completed, total_score, total_turns,
            average_score, average_turns) = Game.games_stats(games)

        form = UserStatsResultForm(
            games_completed=games_completed,
            total_score=total_score,
            total_turns=total_turns,
            average_score=average_score,
            average_turns=average_turns)
        return form


    @endpoints.method(request_message=HIGH_SCORES_REQUEST,
                      response_message=TotalHighScoresResultForm,
                      path='high_scores',
                      name='high_scores',
                      http_method='POST')
    def get_high_scores(self, request):
        """Returns a list of high scores.  In Shut The Box, lower scores are
        better, so a list of high scores is a list of the scores from lowest to
        highest.  In the case of a tie, order is determined by which game
        finished first.

        The high scores are able to be filtered by dice_operation or
        number_of_tiles.

        :param number_of_tiles (opt): If specified, filters to
        return games with the specified number_of_tiles.
        :type number_of_tiles: enum-{NINE, TWELVE}
        :param dice_operation (opt): If specified, filters to
        return games with the specified dice_operation.
        :type dice_operation: enum-{ADDITION, MULTIPLICATION}
        :param number_of_results (opt): Number of high scores to return
        :type number_of_results: integer. DEFAULT=20

        :returns high_scores: List of games ordered by high scores.  Each game
        contains the parameters below.
        :rtype high_score: list
        :returns score: The final score.
        :rtype score: integer
        :returns username: The user who played this game.
        :rtype username: string
        :returns number_of_tiles: Number of tiles for this game.
        Shut The Box with.
        :rtype number_of_tiles: enum-{NINE, TWELVE}
        :returns dice_operation: Dice operation for this game.
        :rtype dice_operation: enum-{ADDITION, MULTIPLICATION}
        :returns timestamp: The date and time when the game was completed.
        :rtype timestamp:
        :returns message: Helpful error message
        :rtype message: string

        :raises: BadArgumentError"""

        if request.number_of_results < 0:
            return TotalHighScoresResultForm(message="number_of_results must "\
                                             "not be below 0!")
        # Order by the most recent lowest score
        games_query = Game.query()
        games_query = games_query.filter(Game.game_over == True)
        if request.number_of_tiles:
            games_query = games_query.filter(
                Game.number_of_tiles == request.number_of_tiles.number)
        if request.dice_operation:
            games_query = games_query.filter(
                Game.dice_operation == request.dice_operation.name)
        games_query = games_query.order(Game.final_score, -Game.timestamp)
        games = games_query.fetch(limit=request.number_of_results)
        if not games:
            return TotalHighScoresResultForm(message="No games match criteria!")
        return TotalHighScoresResultForm(
            high_scores=[game.to_high_scores_result_form() for game in games])


    @endpoints.method(request_message=LEADERBOARD_REQUEST,
                      response_message=TotalLeaderboardResultForm,
                      path='leaderboard',
                      name='leaderboard',
                      http_method='POST')
    def get_leaderboard(self, request):
        """List of ranked users.  Users are ranked by average_score from low
        to high, and in the case of a tie in average score, the rank is
        determined by lowest average_turns.

        Users are only able to be ranked if they have completed 5 or more
        games.  The leaderboard is able to be filtered by dice operation and/or
        number of tiles.

        :param number_of_tiles (opt): Filters leaderboard by number of tiles.
        :type number_of_tiles: enum-{NINE, TWELVE}
        :param dice_operation (opt): Filters leaderboard by dice operation.
        :type dice_operation: enum-{ADDITION, MULTIPLICATION}
        :param username (opt): If specified returns rank of only that user.
        :type username: string

        :returns ranked_users: List of users ordered by rank.  Each user is
        made up of the parameters below.
        :rtype ranked_users: list
        :returns username: A unique username.
        :rtype username: string
        :returns total_score: Total score of completed games.
        :rtype total_score: integer
        :returns total_turns: Total number of turns for completed games.
        :rtype total_turns: integer
        :returns average_score: Average score from completed games.
        :rtype average_score: float
        :returns average_turns: Average turns from completed games.
        :rtype average_turns: float
        :returns games_completed: Number of games completed.
        :rtype games_completed: integer
        :returns rank: Rank of the user.
        :rtype rank: integer
        :returns message: Helpful error message.
        :rtype message: string

        :raises: NotFoundException"""

        if request.username:
            user = User.query(User.username == request.username).get()
            if not user:
                raise endpoints.NotFoundException(
                        'A user with the name {} does not exist!'.\
                        format(request.username))

        users = User.query().fetch()
        if not users:
            return TotalLeaderboardResultForm(message="No users created yet!")
        # Create an empty leaderboard list.  It will be filled with instances
        #  of the UserStats named tuple
        leaderboard = []
        UserStats = namedtuple('UserStats',
            ['total_score', 'average_score', 'average_turns',
            'games_completed', 'username'])

        for user in users:
            games_query = Game.query(ancestor=user.key)
            # Only use games that are over
            games_query = games_query.filter(Game.game_over == True)

            if request.number_of_tiles:
                games_query = games_query.filter(
                    Game.number_of_tiles == request.number_of_tiles.number)
            if request.dice_operation:
                games_query = games_query.filter(
                    Game.dice_operation == request.dice_operation.name)

            games = games_query.fetch()
            # If this user has played less than 5 games, don't rank them.  Must
            # complete 5 or more games to become ranked, due to the nature of
            # ranking in Shut The Box.  It would be too easy for one user to
            # play one game, get a perfect score, and then suddenly overtake
            # the leaderboard
            if len(games) < 5:
                continue
            (games_completed, total_score, total_turns, average_score,
                average_turns) = Game.games_stats(games)

            user_stats = UserStats(total_score, average_score,
                average_turns, games_completed, user.username)
            leaderboard.append(user_stats)

        # if no users have completed games quit early
        if not leaderboard:
            return TotalLeaderboardResultForm(message="No rankable users"\
                                              "yet!")

        # Now to sort the results in this specific way
        leaderboard.sort(key=attrgetter('average_score', 'average_turns',
                                        'username'))

        # Now to assign rank on the already sorted leaderboard list.  It's not
        # as simple as just using enumerate because of possible ties
        rank = 0
        last_average_score = -1
        last_average_turns = -1
        for n, user in enumerate(leaderboard):
            rank += 1
            # Take into account the tie scenario
            if user.average_score == last_average_score and \
            user.average_turns == last_average_turns:
                rank -= 1
            # Need to put the UserStats object in a list so append will work
            leaderboard[n] = [leaderboard[n]]
            leaderboard[n].append(rank)
            # Save off the last ranked user's statistics
            last_average_score = user.average_score
            last_average_turns = user.average_turns

        # If username is specified, make that the only result in the leaderboard
        if request.username:
            for ranked_user in leaderboard:
                if ranked_user[0].username == request.username:
                    leaderboard = [ranked_user]
            if leaderboard[0][0].username is not request.username:
                return TotalLeaderboardResultForm(
                    message="{} is not ranked yet!".format(request.username))

        # Now loop through the leaderboard one last time and put the content
        # into a form
        forms = []
        for ranked_user in leaderboard:
            user_stats = ranked_user[0]
            rank = ranked_user[1]
            leaderboard_form = UserLeaderboardResultForm(
                username=user_stats.username,
                average_score=user_stats.average_score,
                average_turns=user_stats.average_turns,
                total_score=user_stats.total_score,
                games_completed=user_stats.games_completed,
                rank=rank)
            forms.append(leaderboard_form)
        return TotalLeaderboardResultForm(ranked_users=forms)


    @endpoints.method(request_message=URLSAFE_KEY_REQUEST,
                      response_message=AllTurnsReportResultForm,
                      path='game_history',
                      name='game_history',
                      http_method='POST')
    def get_game_history(self, request):
        """Returns the history of moves for the game passed in, allowing game
        progression to be viewed move by move.

        :param urlsafe_key (req): This is the urlsafe_key returned
        from calling new_game().  It serves as the state token for a single
        game of Shut The Box.
        :type urlsafe_key: string

        :returns turns: A list of turns for a specific game.  Each turn contains
        the parameters below.
        :rtype turns: list
        :returns turn: The turn number.
        :rtype turn: integer
        :returns roll: The dice roll for that turn.
        :rtype roll: list of non-negative integers
        :returns tiles_played: The tiles flipped that turn.
        :rtype tiles_played: a list of non-negative integers.
        :returns score: A running total of the active tiles in play.
        :rtype score: non-negative integer
        :returns game_over: If True, game is over.  If False,
        more turns can be played.
        :rtype game_over: boolean

        :raises: BadRequestException, ValueError"""

        game = get_by_urlsafe(request.urlsafe_key, Game)
        turns = Turn.query(ancestor=game.key).order(Turn.timestamp).fetch()

        # Not all the information is present in the turns object for the game
        # history report.  We need to manipulate the active tiles so that it
        # stores the tiles played, not the tiles on the board.  To do that
        # we loop through the turns and calculate the difference between the
        # active tiles present in the last turn vs the active tiles in the
        # current turn.  We use python sets and set.difference to repurpose
        # active_tiles.  We also score the score of each turn in this new
        # active_tiles because you wouldn't be able to calculate it anymore
        # with active_tiles being repurposed.
        # Ex:
        #     Before:
        #     Loop 1: active_tiles: [1,2,3,4,5,6,7,8,9]
        #     Loop 2: active_tiles: [1,2,3,4,5,6,7,8]
        #     Loop 3: active_tiles: [1,2,3,6,7,8]
        #
        #     After:
        #     Loop 1: active_tiles: [45, []]
        #     Loop 2: active_tiles: [36, [9]]
        #     Loop 3: active_tiles: [27, [4,5]]
        for turn in turns:
            # set last_turn explicitly in the first loop
            if turn.turn == 0:
                last_turn = set(turn.active_tiles)

            current_turn = set(turn.active_tiles)
            tiles_played = list(last_turn.difference(current_turn))
            # Set last_turn now for the next loop
            last_turn = set(turn.active_tiles)

            # Now we are going to repurpose turn.active_tiles to store the
            # score and the tiles played
            score = sum(turn.active_tiles)
            turn.active_tiles = []
            turn.active_tiles.append(score)
            turn.active_tiles.append(tiles_played)
        return AllTurnsReportResultForm(
            turns=[turn.to_turn_report_result_form() for turn in turns])

    # # ONLY UNCOMMENT/IMPORT THE MODULES BELOW IF USING THE test_method
    # @endpoints.method(request_message=INSERT_OR_DELETE_REQUEST,
    #                   response_message=InsertOrDeleteDataResultForm,
    #                   path='test_method',
    #                   name='test_method',
    #                   http_method='POST')
    # def test_method(self, request):
    #     if request.delete_everything:
    #         users = User.query().iter(keys_only=True)
    #         ndb.delete_multi(users)
    #         games = Game.query().iter(keys_only=True)
    #         ndb.delete_multi(games)
    #         turns = Turn.query().iter(keys_only=True)
    #         ndb.delete_multi(turns)
    #         return InsertOrDeleteDataResultForm(message="All Users, Games, "\
    #                                             "Turns deleted!")
    #     # some setup for creating request for new games
    #     version = "v1"
    #     port = 8080
    #     base_url =  "http://localhost:{}/_ah/api/shut_the_box/{}/".\
    #         format(port, version)
    #     new_game_url = base_url + "new_game"
    #     # some setup for creating the games
    #     DICE_OPERATION = ["ADDITION", "MULTIPLICATION"]
    #     NUMBER_OF_TILES = ["NINE", "TWELVE"]
    #
    #     with open("pkg/test_data.JSON") as data_file:
    #         json_data = json.load(data_file)
    #         users = json_data["users"]
    #         turns = json_data["turns"]
    #         for user in users:
    #             new_user = User(
    #                 username=user["username"],
    #                 email=user["email"])
    #             new_user.put()
    #         # Now to create the games
    #         for user in users:
    #             for n in range(20): # create 10 games per user
    #                 dice_operation = random.choice(DICE_OPERATION)
    #                 number_of_tiles = random.choice(NUMBER_OF_TILES)
    #                 create_json = [{
    #                     "dice_operation": dice_operation,
    #                     "number_of_tiles": number_of_tiles,
    #                     "username": user["username"]}]
    #                 outside_request = outside_requests.post(
    #                     url=new_game_url, params=create_json[0])
    #                 raw_urlsafe_key = outside_request.json()["urlsafe_key"]
    #                 game_entity = get_by_urlsafe(raw_urlsafe_key, Game)
    #                 turn_list = random.choice(turns.get(
    #                     dice_operation + number_of_tiles))
    #                 for turn in turn_list.get("turn_list"):
    #                     new_turn = Turn(
    #                         key=Turn.create_turn_key(game_entity.key),
    #                         active_tiles=turn.get("active_tiles"),
    #                         roll=turn.get("roll"),
    #                         turn=turn.get("turn"))
    #                     if turn.get("turn_over"):
    #                         new_turn.turn_over = turn.get("turn_over")
    #                     if turn.get("game_over"):
    #                         new_turn.game_over = turn.get("game_over")
    #                     new_turn.put()
    #                 final_score = turn_list.get("final_score")
    #                 if final_score is not None:
    #                     game_entity.final_score = final_score
    #                     game_entity.game_over = True
    #                     game_entity.put()
    #         return InsertOrDeleteDataResultForm(message="Data added "\
    #                                             "successfully!")
