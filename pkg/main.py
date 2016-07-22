import logging
from pkg import *
from models import User, Game, Turn
from models import CreateUserRequestForm, StringMessage
from models import NewGameRequestForm, GameResultForm
from models import TurnRequestForm, TurnResultForm
from models import UserRequestForm, UserStatsResultForm
from models import AllGamesForm, GamesStatusResultForm
from models import URLSafeKeyRequestForm, TurnsStatusForm, CancelResultForm
from models import LeaderboardRequestForm, LeaderboardsResultForm
from models import LeaderboardResultForm
from utils import get_by_urlsafe
from collections import namedtuple
from operator import attrgetter

CREATE_USER_REQUEST = endpoints.ResourceContainer(CreateUserRequestForm)
NEW_GAME_REQUEST = endpoints.ResourceContainer(NewGameRequestForm)
TURN_REQUEST = endpoints.ResourceContainer(TurnRequestForm,
    urlsafe_key=messages.StringField(1))
USER_REQUEST = endpoints.ResourceContainer(UserRequestForm)
ALL_GAMES_REQUEST = endpoints.ResourceContainer(AllGamesForm)
URLSAFE_KEY_REQUEST = endpoints.ResourceContainer(
        urlsafe_key=messages.StringField(1))
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

        :param requests.username (req): A unique username.
        :type requests.username: string
        :param requests.email (opt): A unique and valid email.
        :type requests.email: string

        :returns: A message confirming user was created.
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
        """Creates new game.

        :param request.username (req): A unique username.
        :type request.username: string
        :param request.number_of_tiles (req): Number of active tiles to play
        Shut The Box with.
        :type request.number_of_tiles: enum-{NINE, TWELVE}
        :param request.dice_operation (req): When two dice are rolled in a
        turn, this determines if the number to aim for with the flipped tiles is the sum of the dice roll or the product.
        :type request.dice_operation: enum-{ADDITION, MULTIPLICATION}

        :returns: The username, number_of_tiles, dice_operation, urlsafe_key,
        and message.
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

        First call turn() with only a urlsafe_key and flip_tiles=null.  It
        returns a roll and a full set of tiles.
        Each subsequent call of turn() should include a urlsafe_key and
        flip_tiles, and turn() will determine the validity of the tiles being
        flipped and compute the next roll.

        :param request.urlsafe_key (req): This is the urlsafe_key returned
        from calling new_game().  It serves as the state token for a single
        game of Shut The Box.
        :type request.urlsafe_key: string
        :param request.flip_tiles (opt): Leave this parameter null for
        the first call of turn().  On subsequent calls, flip_tiles are the
        integers to be flipped in response to the roll.
        :type request.flip_tiles: list of non-negative integers

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

    # My view is it's better to just allow people to cancel games outright
    # than to leave them unplayed if they think the score will fare poorly
    # for their average score
    @endpoints.method(request_message=URLSAFE_KEY_REQUEST,
                      response_message=CancelResultForm,
                      path='cancel_game/{urlsafe_key}',
                      name='cancel_game',
                      http_method='DELETE')
    def cancel_game(self, request):
        """Cancels a Game entity and its children Turn entities.
        
        :param request.urlsafe_key (req): This is the urlsafe_key returned
        from calling new_game().  It serves as the state token for a single
        game of Shut The Box.
        :type request.urlsafe_key: string
        
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
        for n in list(reversed(range(2,10))):
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
    def user_stats(self, request):
        """Returns basic user stats.
        
        :param request.username (req): A unique username.
        :type request.username: string
        :param request.number_of_tiles (opt): If filled in, filters to
        return games with the specified number_of_tiles.
        :type request.number_of_tiles: enum-{NINE, TWELVE}
        :param request.dice_operation (opt): If filled in, filters to
        return games with the specified dice_operation.
        :type request.dice_operation: enum-{ADDITION, MULTIPLICATION}

        Returns:

        """
        user = User.query(User.username == request.username).get()
        if not user:
            raise endpoints.NotFoundException(
                    'A user with the name {} does not exist!'.\
                    format(request.username))

        games_query = Game.query(ancestor=user.key)
        games_query = games_query.filter(Game.game_over == True)

        if request.number_of_tiles:
            games_query = games_query.filter(
                Game.number_of_tiles == request.number_of_tiles.number)

        if request.dice_operation:
            games_query = games_query.filter(
                Game.dice_operation == request.dice_operation.name)

        games = games_query.fetch()
        if not games:
            return UserStatsResultForm(message="No games found!")

        (games_played, cumulative_score, cumulative_number_of_turns,
            average_score, average_number_of_turns) = Game.games_stats(games)


        form =  UserStatsResultForm(
            games_played=games_played,
            cumulative_score=cumulative_score,
            cumulative_number_of_turns=cumulative_number_of_turns,
            average_score=average_score,
            average_number_of_turns=average_number_of_turns,
            message="Games found!")
        return form

    # This method, like user_stats, should probably be a GET.  Same gripes.
    @endpoints.method(request_message=ALL_GAMES_REQUEST,
                      response_message=GamesStatusResultForm,
                      path='all_games',
                      name='all_games',
                      http_method='POST')
    def all_games(self, request):
        if request.username:
            user = User.query(User.username == request.username).get()
            if not user:
                raise endpoints.NotFoundException(
                        'A user with the name {} does not exist!'.\
                        format(request.username))
            # if username is passed in, look for only their games
            games_query = Game.query(ancestor=user.key)
        # Otherwise, just return all the games
        else:
            games_query = Game.query()

        if request.active_games == True \
            and request.finished_games == True:
            raise endpoints.BadRequestException("all_games() can't be called with"
                " the parameters active_games and finished_games both True")

        if request.active_games:
            games_query = games_query.filter(Game.game_over == False)
        if request.finished_games:
            games_query = games_query.filter(Game.game_over == True)
        # Return the most recent games first
        games_query = games_query.order(-Game.timestamp)
        games = games_query.fetch()

        return GamesStatusResultForm(
            items=[game.to_game_status_result_form() for game in games])


    @endpoints.method(request_message=URLSAFE_KEY_REQUEST,
                      response_message=TurnsStatusForm,
                      path='play_by_play',
                      name='play_by_play',
                      http_method='POST')
    def play_by_play(self, request):
        game = get_by_urlsafe(request.urlsafe_key, Game)
        turns = Turn.query(ancestor=game.key).order(Turn.timestamp).fetch()
        return TurnsStatusForm(
            items=[turn.to_turn_status_form() for turn in turns])

# class LeaderboardRequestForm(messages.Message):
#     number_of_tiles = messages.EnumField('NumberOfTiles', 1)
#     dice_operation = messages.EnumField('DiceOperation', 2)
#     use_total_score = messages.BooleanField(3, default=True)
#     use_average_game_score = messages.BooleanField(4, default=False)
#
#
# class LeaderBoardResultForm(messages.Message):
#     username = messages.StringField(1, required=True)
#     total_score = messages.IntegerField(2)
#     average_score = messages.IntegerField(3)
#     games_played = messages.IntegerField(4)
#
#
# class LeaderBoardsResultForm(messages.Message):
#     items = messages.MessageField(LeaderBoardResultForm, 1, repeated=True)
#     filters = messages.StringField(2)
    @endpoints.method(request_message=LEADERBOARD_REQUEST,
                      response_message=LeaderboardsResultForm,
                      path='leaderboard',
                      name='leaderboard',
                      http_method='POST')
    def leaderboard(self, request):
        users = User.query().fetch()
        if not users:
            return LeaderboardsResultForm(message="No users created yet!")
        logging.warning(users)
        users = iter(users)
        leaderboard = []
        UserStats = namedtuple('UserStats',
            ['score', 'games_played', 'username'])
        for user in users:
            games_query = Game.query(ancestor=user.key)
            games_query = games_query.filter(Game.game_over == True)

            if request.number_of_tiles:
                games_query = games_query.filter(
                    Game.number_of_tiles == request.number_of_tiles.number)

            if request.dice_operation:
                games_query = games_query.filter(
                    Game.dice_operation == request.dice_operation.name)

            games = games_query.fetch()
            if not games:
                continue
            (games_played, cumulative_score,
                cumulative_number_of_turns, average_score,
                average_number_of_turns) = Game.games_stats(games)


            if request.use_cumulative_score:
                user_stats = UserStats(
                    float(cumulative_score), games_played, user.username)
            else:
                user_stats = UserStats(
                    average_score, games_played, user.username)
            leaderboard.append(user_stats)

        if not leaderboard:
            return LeaderboardsResultForm(message="No games played yet!")
        # Now to sort the results
        logging.warning(leaderboard)
        leaderboard.sort(key=attrgetter('score'))
        logging.warning(leaderboard)

        forms  = []
        for user in leaderboard:
            leaderboard_form = LeaderboardResultForm(
                username=user.username,
                games_played=user.games_played,
                score=user.score)
            forms.append(leaderboard_form)
        message = "Users Found!"
        if request.dice_operation:
            message += " | Filter: dice_operation == {}"\
                .format(request.dice_operation.name)
        if request.number_of_tiles:
            message += " | Filter: number_of_tiles == {}"\
                .format(request.number_of_tiles.number)
        if request.use_cumulative_score:
            message += " | use_cumulative_score == True"
        return LeaderboardsResultForm(items=forms, message=message)
