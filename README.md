# ShutTheBox
A traditional pub game using dice and a counting box with numbered tiles for one or more players, often involving stakes


Plays one turn of Shut The Box.

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

:raises: BadRequestException, ValueError
