import logging
from pkg import *
from models import User, Game, Turn
from models import CreateUserRequestForm, StringMessage
from models import NewGameRequestForm, GameResultForm
from models import TurnRequestForm, TurnResultForm
from models import UserRequestForm, UserStatsResultForm
from models import GamesRequestForm, GamesStatusResultForm
from models import URLSafeKeyRequestForm, TurnsStatusForm, CancelResultForm
from models import HighScoresRequestForm, TotalHighScoresResultForm
from models import LeaderboardRequestForm, TotalLeaderboardResultForm
from models import UserLeaderboardResultForm
from utils import get_by_urlsafe
from collections import namedtuple
from operator import attrgetter

CREATE_USER_REQUEST = endpoints.ResourceContainer(CreateUserRequestForm)
NEW_GAME_REQUEST = endpoints.ResourceContainer(NewGameRequestForm)
TURN_REQUEST = endpoints.ResourceContainer(TurnRequestForm,
    urlsafe_key=messages.StringField(1))
USER_REQUEST = endpoints.ResourceContainer(UserRequestForm)
GAMES_REQUEST = endpoints.ResourceContainer(GamesRequestForm)
URLSAFE_KEY_REQUEST = endpoints.ResourceContainer(
        urlsafe_key=messages.StringField(1))
HIGH_SCORES_REQUEST = endpoints.ResourceContainer(HighScoresRequestForm)
LEADERBOARD_REQUEST = endpoints.ResourceContainer(LeaderboardRequestForm)

@endpoints.api(name='shut_the_box', version='v1')
class ShutTheBoxApi(remote.Service):
    """A set of methods implementing the gameplay of the classic British pub
    game Shut The Box.  The entire game is implemented on the server-side
    through Google's Cloud Endpoints.  The state of a game is remembered by
    passing an individual game's entity key to the client, serving as a state
    token."""
    @endpoints.method(request_message=CREATE_USER_REQUEST,
                      response_message=StringMessage,
                      path='user',
                      name='create_user',
                      http_method='POST')
    def create_user(self, request):
        """Creates a User.

        :param username (req): A unique username without leading spaces.
        :type username: string
        :param email (opt): A unique and valid email.  Email is validated using MAILGUN email validation API.
        :type email: string

        :returns message (req): A message confirming user was created, or an error message.
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
                return StringMessage(
                    message="Email address invalid! User is not created.")
            # All is good, saving User object
            user = User(
                username=request.username,
                email=request.email)
            user.put()
        else:
            user = User(
                username = request.username)
            user.put()
        return StringMessage(message='User {} created!'.
                             format(request.username))


    @endpoints.method(request_message=NEW_GAME_REQUEST,
                      response_message=GameResultForm,
                      path='game',
                      name='new_game',
                      http_method='POST')
    def new_game(self, request):
        """Creates a new game.

        :param username (req): A unique username.
        :type username: string
        :param number_of_tiles (req): Number of tiles to play
        Shut The Box with.
        :type number_of_tiles: enum-{NINE, TWELVE}
        :param dice_operation (req): When two dice are rolled in a
        turn, this determines if the number to aim for with the flipped tiles is the sum of the dice roll or the product.
        :type dice_operation: enum-{ADDITION, MULTIPLICATION}

        :returns username (req): A unique username.
        :rtype username: string
        :returns number_of_tiles (req): Number of tiles to play Shut The Box with.
        :rtype number_of_tiles: enum-{NINE, TWELVE}
        :returns dice_operation (req): When two dice are rolled in a
        turn, this determines if the number to aim for with the flipped tiles is the sum of the dice roll or the product.
        :rtype dice_operation: enum-{ADDITION, MULTIPLICATION}
        :returns urlsafe_key (req): This is the urlsafe_key returned
        from calling new_game().  It serves as the state token for a single
        game of Shut The Box.
        :rtype urlsafe-key: string
        :returns message (req): A helpful message or an error message.
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
        return game.to_game_result_form("Good luck playing Shut The Box, {}!".
                                        format(user.username))


    @endpoints.method(request_message=TURN_REQUEST,
                      response_message=TurnResultForm,
                      path='game/{urlsafe_key}',
                      name='turn',
                      http_method='PUT')
    def turn(self, request):
        """Plays one turn of Shut The Box.

        To play Shut The Box, first call turn() with only a urlsafe_key and flip_tiles null.  It returns a roll and a full set of tiles.
        Each subsequent call of turn() must include both a urlsafe_key and
        flip_tiles, and turn() will determine the validity of flip_tiles and compute the next roll.  The goal is to flip all the tiles and get the lowest score possible.

        :param urlsafe_key (req): This is the urlsafe_key returned
        from calling new_game().  It serves as the state token for a single
        game of Shut The Box.
        :type urlsafe_key: string
        :param flip_tiles (opt): Leave this parameter null for
        the first call of turn().  On subsequent calls, flip_tiles are the
        integers to be flipped in response to the roll.
        :type flip_tiles: list of non-negative integers

        :returns urlsafe_key (req): The same urlsafe_key passed in.
        :rtype urlsafe_key: string
        :returns roll (opt): Returns a list of two integers between 1-6 if
        the active_tiles above 7 are in play.  If all tiles 7 and above are
        not active, returns a list of 1 integer between 1-6.  No roll is
        returned in the case of a perfect score.
        :rtype roll: list of non-negative integers
        :returns active_tiles (opt): The active_tiles left after the roll has
        been played.
        :rtype active_tiles: a list of non-negative integers
        :returns valid_move (req): True if flip_tiles played are valid,
        False if they are not valid.  If False, new turn is not created.
        :rtype valid_move: boolean
        :returns score (opt): a running sum of the active_tiles in play
        :rtype score: non-negative integer
        :returns game_over (req): If True, game is over.  If False,
        more turns can be played.
        :rtype game_over: boolean
        :returns message (req): Helpful message.
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
        recent_turn = game.most_recent_turn()
        if not recent_turn:
            # If recent_turn is null, this is the first roll!
            turn = Turn.first_roll(game)
            return turn.to_form(
                urlsafe_key=game.key.urlsafe(),
                valid_move=True,
                message="Call turn() again to play your roll")
        # If it's not a user's first turn, user must pass in flip_tiles
        if not request.flip_tiles:
            return recent_turn.to_form(
                urlsafe_key=game.key.urlsafe(),
                valid_move=False,
                message="User must pass in values to flip_tiles!")
        # Check if it's a valid flip
        error = recent_turn.invalid_flip(request.flip_tiles,
                                         game.dice_operation)
        if error:
            return recent_turn.to_form(
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
            return new_turn.to_form(
                urlsafe_key=game.key.urlsafe(),
                valid_move=True,
                message="Game over! Perfect score! Call new_game() to play again!")
        # Check if the roll from the new turn ends the game
        game_over = new_turn.is_game_over(game)
        if game_over:
            new_turn.end_game(game)
            return new_turn.to_form(
                urlsafe_key=game.key.urlsafe(),
                valid_move=True,
                message="Game over! Call new_game() to play again!")
        # If the code's fallen through to here, the roll is valid
        return new_turn.to_form(
            urlsafe_key=game.key.urlsafe(),
            valid_move=True,
            message="Call turn() again to play your roll")


    # cancel_game just deletes the game/turns.  My view is it's better to just
    # allow people to cancel games outright than to mark them somehow in the
    # database
    @endpoints.method(request_message=URLSAFE_KEY_REQUEST,
                      response_message=CancelResultForm,
                      path='cancel_game/{urlsafe_key}',
                      name='cancel_game',
                      http_method='DELETE')
    def cancel_game(self, request):
        """Cancels a Game entity and its children Turn entities.  User can only cancel games in progress.

        :param urlsafe_key (req): This is the urlsafe_key returned
        from calling new_game().  It serves as the state token for a single
        game of Shut The Box.
        :type urlsafe_key: string

        :returns cancelled (req): True if the game entity and Turn entities are
        deleted from the datastore; False if the game entity in question is
        already completed.
        :rtype cancelled: boolean
        :returns error (opt): Helpful error message.
        :rtype error: string

        :raises: BadRequestException, ValueError"""

        game = get_by_urlsafe(request.urlsafe_key, Game)
        if game.game_over:
            return CancelResultForm(
                cancelled=False,
                error="Can't cancel games that are already completed.")
        # This deletes both the parent game and the children turns
        ndb.delete_multi(ndb.Query(ancestor=game.key).iter(keys_only = True))
        return CancelResultForm(cancelled=True)


    @endpoints.method(request_message=TURN_REQUEST,
                      response_message=TurnResultForm,
                      path='turnfix',
                      name='turnfix',
                      http_method='POST')
    def turnfix(self, request):
        game = get_by_urlsafe(request.urlsafe_key, Game)
        turn = Turn()
        first_turn = Turn(
            key=turn.create_turn_key(game.key),
            turn=0,
            roll=[9],
            active_tiles=range(1, 10))
        first_turn.put()
        for n in list(reversed(range(3,9))):
            recent_turn = game.most_recent_turn()
            new_turn = Turn(
                key=recent_turn.create_turn_key(game.key),
                turn=recent_turn.turn + 1,
                roll=[n-1],
                active_tiles=recent_turn.flip([n]))
            new_turn.put()
        return new_turn.to_form(
            urlsafe_key=game.key.urlsafe(),
            valid_move=True,
            message="Call turn() again to play your roll")


    # TODO: For the life of me, I could not figure out how to make this
    # method into a GET request with multiple query parameters (username,
    # number_of_dice, dice_operation).  I was able to figure out how to do it
    # with one parameter, but not multiple.  And the google tutorial only
    # features GETs with 1 parameter.
    # https://github.com/GoogleCloudPlatform/python-docs-samples/blob/master/appengine/standard/endpoints/backend/main.py
    # It is also possible to just make many different user_stats APIs
    # that are GETS with number_of_tiles or dice_operation hard-set
    @endpoints.method(request_message=USER_REQUEST,
                      response_message=UserStatsResultForm,
                      path='user_stats',
                      name='user_stats',
                      http_method='POST')
    def get_user_stats(self, request):
        """Returns basic user statistics.

        The statistics are completed games, total score, total turns, average score, and average turns.  Able to filter by username, dice operation, and number of dice.

        :param username (req): A unique username.
        :type username: string
        :param number_of_tiles (opt): If specified, filters to
        return games with the specified number_of_tiles.
        :type number_of_tiles: enum-{NINE, TWELVE}
        :param dice_operation (opt): If specified, filters to
        return games with the specified dice_operation.
        :type dice_operation: enum-{ADDITION, MULTIPLICATION}

        :returns games_completed (req): Number of games completed
        :rtype games_completed: integer
        :returns total_score (req): Total score of completed games
        :rtype total_score: integer
        :returns total_turns (req): Total number of turns for all completed games
        :returns average_score (req): Average score from all completed games
        :rtype average_score: float
        :returns average_turns (req): Average turns from all completed games
        :rtype average_turns: float
        :returns message (opt): Error message
        :rtype message: string

        :raises: NotFoundException"""

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

        form =  UserStatsResultForm(
            games_completed=games_completed,
            total_score=total_score,
            total_turns=total_turns,
            average_score=average_score,
            average_turns=average_turns)
        return form


    # TODO: This method, like user_stats, should probably be a GET.
    # The rubric calls for a method get_user_games, but I expanded this API to
    # have that functionality and more
    @endpoints.method(request_message=GAMES_REQUEST,
                      response_message=GamesStatusResultForm,
                      path='games_report',
                      name='games_report',
                      http_method='POST')
    def games_report(self, request):
        """Returns all games by default.

        Each game is returned with its urlsafe key, the number of tiles and dice operation selected for the game, and whether the game is over or not.  Able to filter by username, number of tiles, and dice operation. User is not able to call games_report with both parameters games_in_progress and finished_games True, as that would be a contradiction.

        :param games_in_progress (opt): If True, returns active games.  If False, returns both active games finished games.
        :type games_in_progress: boolean
        :param finished_games (opt): If True, returns only finished games. If False, returns both active games and finished games.
        :type finished_games: boolean
        :param username (opt): A unique username.
        :type username: string

        :returns games (req): A list of games. Each game contains the parameters below.
        :rtype games: list
        :returns urlsafe_key (req): The urlsafe_key used to play the game.
        :rtype urlsafe_key: string
        :returns number_of_tiles (req): Number of tiles to play
        Shut The Box with.
        :rtype number_of_tiles: enum-{NINE, TWELVE}
        :returns dice_operation (req): When two dice are rolled in a
        turn, this determines if the number to aim for with the flipped tiles is the sum of the dice roll or the product.
        :rtype dice_operation: enum-{ADDITION, MULTIPLICATION}
        :returns game_over (req): If True, game is over.  If False,
        more turns can be played.
        :rtype game_over: boolean
        :returns turns_played (req): Number of turns played.
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
        # Otherwise, just return all the games
        else:
            games_query = Game.query()

        if request.games_in_progress == True \
        and request.finished_games == True:
            raise endpoints.BadRequestException("games_report can't be called "
            "with both parameters games_in_progress and finished_games True")

        if request.games_in_progress:
            games_query = games_query.filter(Game.game_over == False)
        if request.finished_games:
            games_query = games_query.filter(Game.game_over == True)
        # Return the most recent games first
        games_query = games_query.order(-Game.timestamp)
        games = games_query.fetch()

        return GamesStatusResultForm(
            games=[game.to_game_status_result_form() for game in games])


    @endpoints.method(request_message=URLSAFE_KEY_REQUEST,
                      response_message=TurnsStatusForm,
                      path='game_history',
                      name='game_history',
                      http_method='POST')
    def get_game_history(self, request):
        """Returns the history of moves for the game passed in, allowing a game to be replayed and watched move by move.

        :param urlsafe_key (req): This is the urlsafe_key returned
        from calling new_game().  It serves as the state token for a single
        game of Shut The Box.
        :type urlsafe_key: string

        :returns turns (req): A list of turns for a specific game.  Each turn contains the parameters below.
        :rtype turns: list
        :returns turn (req): The turn number.
        :rtype turn: integer
        :returns roll (req): A list of the dice roll.
        :rtype roll: list of non-negative integers
        :returns tiles_played (req): The tiles flipped that turn.
        :rtype tiles_played: a list of non-negative integers.
        :returns score (opt): a running sum of the active_tiles in play
        :rtype score: non-negative integer
        :returns game_over (req): If True, game is over.  If False,
        more turns can be played.
        :rtype game_over: boolean

        :raises: BadRequestException, ValueError"""

        game = get_by_urlsafe(request.urlsafe_key, Game)
        turns = Turn.query(ancestor=game.key).order(Turn.timestamp).fetch()

        for turn in turns:
            if turn.turn == 0: # Only set last_turn in the first loop
                last_turn = set(turn.active_tiles)
            current_turn = set(turn.active_tiles)
            tiles_played = list(last_turn.difference(current_turn))
            # Set last_turn now for the next loop / the next comparison
            last_turn = set(turn.active_tiles)
            # Now we are going to repurpose turn.active_tiles, a variable
            # associated with each turn, to store the score and the tiles_played
            score = sum(turn.active_tiles)
            turn.active_tiles = []
            turn.active_tiles.append(score)
            turn.active_tiles.append(tiles_played)
        return TurnsStatusForm(
            turns=[turn.to_turn_status_form() for turn in turns])

# # Section for get_high_scores method
# class HighScoreRequestForm(messages.Message):
#     number_of_tiles = messages.EnumField('NumberOfTiles', 1)
#     dice_operation = messages.EnumField('DiceOperation', 2)
#     number_of_results = messages.IntegerField(3)
#
#
# class GameHighScoreResultForm(messages.Message):
#     score = messages.IntegerField(1)
#     username = messages.StringField(2)
#     number_of_tiles = messages.IntegerField(3)
#     dice_operation = messages.StringField(4)
#     timestamp = message_types.DateTimeField(5)
#
#
# class TotalHighScoreResultForm(messages.Message):
#     high_scores = messages.MessageField(GameHighScoreResultForm, 1,
#         repeated=True)
#     message = messages.StringField(2)
    @endpoints.method(request_message=HIGH_SCORES_REQUEST,
                      response_message=TotalHighScoresResultForm,
                      path='high_scores',
                      name='high_scores',
                      http_method='POST')
    def get_high_scores(self, request):
        """List of high scores.  In Shut The Box, lower scores are better, so a list of high scores is a list of the scores from lowest to highest.  In the case of a tie, order is determined by which game finished first.

        The high scores are able to be filtered by dice_operation or number_of_tiles.

        :param number_of_tiles (opt): If specified, filters to
        return games with the specified number_of_tiles.
        :type number_of_tiles: enum-{NINE, TWELVE}
        :param dice_operation (opt): If specified, filters to
        return games with the specified dice_operation.
        :type dice_operation: enum-{ADDITION, MULTIPLICATION}
        :param number_of_results (opt): Number of high scores to return
        :type number_of_results: integer. DEFAULT=20

        :returns high_scores: List of games ordered by high scores.  Each game contains the parameters below.
        :rtype high_score: list
        :returns score: The final score.
        :rtype score: integer
        :returns username: A unique username.
        :rtype username: string
        :returns number_of_tiles: Number of tiles to play
        Shut The Box with.
        :rtype number_of_tiles: enum-{NINE, TWELVE}
        :returns dice_operation: When two dice are rolled in a
        turn, this determines if the number to aim for with the flipped tiles is the sum of the dice roll or the product.
        :rtype dice_operation: enum-{ADDITION, MULTIPLICATION}
        :returns timestamp: The date/time which the game was completed.
        :rtype timestamp: 
        :returns message: Error message
        :rtype message: string

        :raises: BadArgumentError
        """
        # Order by the most recent lowest score
        games_query = Game.query().order(Game.final_score, -Game.timestamp)
        games_query = games_query.filter(Game.game_over == True)
        if request.number_of_tiles:
            games_query = games_query.filter(
                Game.number_of_tiles == request.number_of_tiles.number)
        if request.dice_operation:
            games_query = games_query.filter(
                Game.dice_operation == request.dice_operation.name)

        games = games_query.fetch(limit=request.number_of_results)
        if not games:
            return TotalHighScoresResultForm(message="No games match criteria!")
        return TotalHighScoresResultForm(
            high_scores=[game.to_high_score_form() for game in games])


    @endpoints.method(request_message=LEADERBOARD_REQUEST,
                      response_message=TotalLeaderboardResultForm,
                      path='leaderboard',
                      name='leaderboard',
                      http_method='POST')
    def get_user_rankings(self, request):
        """List of ranked players.  Players are ranked by average_score from low to high, and in the case of a tie in average_score, the rank is determined by lowest average_turns.

        Players are only able to be ranked if they have completed 5 or more games.  The leaderboard is able to be filtered by dice_operation or number_of_tiles.

        :param number_of_tiles (opt): If specified, filters to
        return games with the specified number_of_tiles.
        :type number_of_tiles: enum-{NINE, TWELVE}
        :param dice_operation (opt): If specified, filters to
        return games with the specified dice_operation.
        :type dice_operation: enum-{ADDITION, MULTIPLICATION}

        :returns username (req): A unique username.
        :rtype username: string
        :returns total_turns (req): Total number of turns for all completed games
        :returns average_score (req): Average score from all completed games
        :rtype average_score: float
        :returns average_turns (req): Average turns from all completed games
        :rtype average_turns: float
        :returns total_score (req): Total score of completed games
        :rtype total_score: integer
        :returns games_completed (req): Number of games completed
        :rtype games_completed: integer
        :returns rank (req): Rank of the user.
        :rtype rank: integer
        :returns message (opt): Error message
        :rtype message: string"""

        users = User.query().fetch()
        if not users:
            return TotalLeaderboardResultForm(message="No users created yet!")
        # Create an empty leaderboard list and populate it with the UserStats
        # namedtuple
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
            # ranking in Shut The Box.  It would be too easy for one player to
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
            return TotalLeaderboardResultForm(message="No rankable players yet!")
        # TODO: Think about sorting the results in parts to save time and
        # processing power
        # Now to sort the results
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
        # Now loop through the leaderboard one last time and put the content
        # into a form
        forms  = []
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
