"""
command.py

PURPOSE: Define the Command model and Verb/Preposition enums for parsed player input.
DEPENDENCIES: None (pure Python + enum)

ARCHITECTURE NOTES:
Commands represent fully parsed player input. The parser produces Command objects,
and the game engine consumes them. This provides a clean boundary between parsing
and execution.
"""

from dataclasses import dataclass
from enum import Enum, auto


class Verb(Enum):
    """
    All verbs supported by the game engine.

    Movement verbs are directions (NORTH, SOUTH, etc.) as well as GO.
    Object manipulation verbs require at least a direct object.
    Meta verbs affect the game session rather than game state.
    """

    # Movement
    GO = auto()
    NORTH = auto()
    SOUTH = auto()
    EAST = auto()
    WEST = auto()
    UP = auto()
    DOWN = auto()
    IN = auto()
    OUT = auto()

    # Object manipulation
    TAKE = auto()  # aliases: GET, GRAB, PICK UP
    DROP = auto()  # aliases: PUT DOWN, DISCARD
    PUT = auto()  # PUT X IN/ON Y
    GIVE = auto()  # GIVE X TO Y

    # Examination
    EXAMINE = auto()  # aliases: LOOK AT, X, INSPECT
    READ = auto()

    # Container/lock operations
    OPEN = auto()
    CLOSE = auto()
    LOCK = auto()
    UNLOCK = auto()

    # Tool use
    USE = auto()  # USE X WITH Y

    # Interaction
    TALK = auto()  # TALK TO X
    SHOW = auto()  # SHOW X TO Y
    SING = auto()  # SING
    INSERT = auto()  # INSERT X (custom action)

    # Inventory
    INVENTORY = auto()  # aliases: I, INV

    # Meta commands
    LOOK = auto()  # aliases: L (describe current room)
    QUIT = auto()  # aliases: Q, EXIT
    HELP = auto()
    SAVE = auto()
    LOAD = auto()
    WAIT = auto()  # aliases: Z

    # Custom verbs defined in game JSON
    CUSTOM = auto()  # Placeholder for game-defined verbs


class Preposition(Enum):
    """Prepositions that connect direct and indirect objects."""

    IN = auto()  # PUT key IN box
    ON = auto()  # PUT book ON table
    WITH = auto()  # UNLOCK door WITH key
    TO = auto()  # GIVE coin TO merchant
    FROM = auto()  # TAKE apple FROM basket
    AT = auto()  # LOOK AT painting
    UNDER = auto()  # LOOK UNDER bed


@dataclass(frozen=True)
class Command:
    """
    A fully parsed player command.

    Examples:
        - NORTH -> Command(verb=NORTH)
        - TAKE LAMP -> Command(verb=TAKE, direct_object="lamp")
        - PUT KEY IN BOX -> Command(verb=PUT, direct_object="key",
                                    preposition=IN, indirect_object="box")
        - EXAMINE THE BRASS KEY -> Command(verb=EXAMINE, direct_object="brass key")
        - PRAY -> Command(verb=CUSTOM, custom_verb="pray")

    Attributes:
        verb: The action to perform (CUSTOM for game-defined verbs)
        direct_object: The primary object of the action (optional)
        preposition: Connects direct and indirect objects (optional)
        indirect_object: Secondary object, usually the target/container (optional)
        raw_input: The original player input string
        custom_verb: The actual verb name when verb=CUSTOM (optional)
    """

    verb: Verb
    direct_object: str | None = None
    preposition: Preposition | None = None
    indirect_object: str | None = None
    raw_input: str = ""
    custom_verb: str | None = None  # Actual verb name when verb=CUSTOM

    def __post_init__(self) -> None:
        """Validate command structure."""
        # If there's an indirect object, there must be a preposition
        if self.indirect_object and not self.preposition:
            raise ValueError("Command has indirect_object but no preposition")
        # If there's a preposition, there should be both objects
        if self.preposition and not (self.direct_object and self.indirect_object):
            raise ValueError("Command with preposition requires both direct and indirect objects")


# Verb aliases for the parser
VERB_ALIASES: dict[str, Verb] = {
    # Movement
    "go": Verb.GO,
    "walk": Verb.GO,
    "move": Verb.GO,
    "n": Verb.NORTH,
    "north": Verb.NORTH,
    "s": Verb.SOUTH,
    "south": Verb.SOUTH,
    "e": Verb.EAST,
    "east": Verb.EAST,
    "w": Verb.WEST,
    "west": Verb.WEST,
    "u": Verb.UP,
    "up": Verb.UP,
    "d": Verb.DOWN,
    "down": Verb.DOWN,
    "in": Verb.IN,
    "enter": Verb.IN,
    "out": Verb.OUT,
    "exit": Verb.OUT,
    "leave": Verb.OUT,
    # Object manipulation
    "take": Verb.TAKE,
    "get": Verb.TAKE,
    "grab": Verb.TAKE,
    "pick": Verb.TAKE,  # "pick up" handled specially
    "drop": Verb.DROP,
    "put": Verb.PUT,
    "place": Verb.PUT,
    "give": Verb.GIVE,
    # Examination
    "examine": Verb.EXAMINE,
    "x": Verb.EXAMINE,
    "look": Verb.LOOK,  # "look at" handled specially
    "l": Verb.LOOK,
    "inspect": Verb.EXAMINE,
    "read": Verb.READ,
    # Container/lock
    "open": Verb.OPEN,
    "close": Verb.CLOSE,
    "shut": Verb.CLOSE,
    "lock": Verb.LOCK,
    "unlock": Verb.UNLOCK,
    # Tool use
    "use": Verb.USE,
    # Interaction
    "talk": Verb.TALK,
    "speak": Verb.TALK,
    "say": Verb.TALK,
    "show": Verb.SHOW,
    "present": Verb.SHOW,
    "display": Verb.SHOW,
    "sing": Verb.SING,
    "insert": Verb.INSERT,
    # Inventory
    "inventory": Verb.INVENTORY,
    "i": Verb.INVENTORY,
    "inv": Verb.INVENTORY,
    # Meta
    "quit": Verb.QUIT,
    "q": Verb.QUIT,
    "help": Verb.HELP,
    "?": Verb.HELP,
    "save": Verb.SAVE,
    "load": Verb.LOAD,
    "restore": Verb.LOAD,
    "wait": Verb.WAIT,
    "z": Verb.WAIT,
}

# Preposition mappings
PREPOSITION_WORDS: dict[str, Preposition] = {
    "in": Preposition.IN,
    "into": Preposition.IN,
    "inside": Preposition.IN,
    "on": Preposition.ON,
    "onto": Preposition.ON,
    "upon": Preposition.ON,
    "with": Preposition.WITH,
    "using": Preposition.WITH,
    "to": Preposition.TO,
    "from": Preposition.FROM,
    "at": Preposition.AT,
    "under": Preposition.UNDER,
    "beneath": Preposition.UNDER,
    "below": Preposition.UNDER,
}

# Direction verbs that don't require "GO" prefix
DIRECTION_VERBS: set[Verb] = {
    Verb.NORTH,
    Verb.SOUTH,
    Verb.EAST,
    Verb.WEST,
    Verb.UP,
    Verb.DOWN,
    Verb.IN,
    Verb.OUT,
}

# Verbs that require a direct object
VERBS_REQUIRING_OBJECT: set[Verb] = {
    Verb.TAKE,
    Verb.DROP,
    Verb.PUT,
    Verb.GIVE,
    Verb.EXAMINE,
    Verb.READ,
    Verb.OPEN,
    Verb.CLOSE,
    Verb.LOCK,
    Verb.UNLOCK,
    Verb.USE,
    Verb.TALK,
    Verb.SHOW,
    Verb.INSERT,
}

# Verbs that can take a preposition and indirect object
VERBS_WITH_INDIRECT: set[Verb] = {
    Verb.PUT,  # PUT X IN/ON Y
    Verb.GIVE,  # GIVE X TO Y
    Verb.UNLOCK,  # UNLOCK X WITH Y
    Verb.LOCK,  # LOCK X WITH Y
    Verb.USE,  # USE X WITH/ON Y
    Verb.SHOW,  # SHOW X TO Y
    Verb.INSERT,  # INSERT X IN/INTO Y
}
