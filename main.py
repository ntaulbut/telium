from random import randint, choice
from typing import Callable, Optional, Any

from definitions import *
from utils import *

# Constants
MODULES_FILE = "data/space_modules.json"
# Gameplay constants
NUM_WORKER_ALIENS = 4
LOCK_MODULE_ENERGY = 20

# Available commands handling
available_commands: Dict[str, Callable] = {}
command_helps: List[str] = []


def get_dialogue(key: str) -> str:
    return choice(dialogue[key])


def command(word: str) -> Callable:
    """Register a command."""

    def wrap(func: Callable) -> Callable:
        available_commands[word] = func
        if func.__doc__ is not None:
            command_helps.append(func.__doc__)
        return func

    return wrap


@command("quit")
def quit_game(_) -> None:
    """quit: Quit the game."""
    if yes_or_no("Are you sure you want to quit? Your progress will be lost."):
        quit()
    else:
        cprint("Quit cancelled.")


@command("commands")
def list_available_commands(_) -> None:
    """commands: List the available commands."""
    cprint("You can use these commands:")
    for command_help in command_helps:
        cprint(" - " + command_help, long_delay=0.02)


@command("doors")
def print_doors(_) -> None:
    """doors: List the available doors."""
    player.module.print_doors()


@command("debug")
def debug(_) -> None:
    breakpoint()


@command("modules")
def list_modules(_) -> None:
    """modules: List the modules in the station."""
    cprint("These modules are in the station:")
    for module_id in station.modules:
        module = ModuleInterface(module_id)
        cprint(f" - {module.title} ({module_id})")


@command("go")
def go_in_direction(args: List[str]) -> bool:
    """go [direction] e.g. northeast/ne: Go through a door."""
    direction: str = args[0]
    if direction in DIRECTION_ALIASES:
        direction = DIRECTION_ALIASES[direction]
    if direction not in DIRECTIONS:
        cprint(f"You remember that '{direction}' is not a compass direction.")
        return False
    try:
        player.move_to(ModuleInterface(player.module.doors[direction]), introduce=True)
        return True
    except KeyError:
        cprint("You bump into the wall.")
        player.module.print_doors()
        return False


@command("lock")
def lock_module(args: List[str]) -> bool:
    """lock [module id] e.g. bridge: Lock a module."""
    try:
        module = ModuleInterface(args[0])
    except AssertionError:
        cprint(f"No such module '{args[0]}', enter `modules` to list them.")
        return False
    if module == player.locked_module:
        cprint("Module is already locked.")
        return False
    if station._energy >= LOCK_MODULE_ENERGY:
        player.locked_module = module
        station.deplete_energy(LOCK_MODULE_ENERGY)
        cprint(f"Successfully locked the {module.title}.")
        return True
    else:
        cprint(f"Insufficient energy to lock the module.")
        return False


@command("stats")
def stats(_) -> None:
    """stats: Show your current stats."""
    player.print_stats()


class ModuleInterface(object):
    """Allows referencing a module directly instead of by indexing the global
    list of modules. Raises an assertion error if it is attempted to be created
    for a module that does not exist."""

    def __init__(self, module_id: str) -> None:
        assert module_id in list(station.modules.keys())
        object.__setattr__(self, "module_id", module_id)

    def __getattribute__(self, name: str) -> Any:
        return station.modules[
            object.__getattribute__(self, "module_id")
        ].__getattribute__(name)

    def __setattr__(self, name: str, value: Any) -> None:
        station.modules[object.__getattribute__(self, "module_id")].__setattr__(
            name, value
        )

    def __eq__(self, other: Any) -> bool:
        # Two ModuleInterfaces are equal if they point to the same module
        if isinstance(other, self.__class__):
            return object.__getattribute__(
                self, "module_id"
            ) == object.__getattribute__(other, "module_id")
        # A ModuleInterface is equal to a string if it's the module id it points to
        elif isinstance(other, str):
            return object.__getattribute__(self, "module_id") == other
        else:
            return False

    def __ne__(self, other: Any) -> bool:
        return not self == other


def random_module(exclude: Optional[List[ModuleInterface]] = None) -> ModuleInterface:
    """Return a random module, optionally excluding some of them."""
    if exclude is None:
        exclude = []
    return ModuleInterface(
        choice(
            [
                module_id
                for module_id in station.modules.keys()
                if ModuleInterface(module_id) not in exclude
            ]
        )
    )


class Module:
    """Space station module."""

    def __init__(self, title: str, description: str, doors: Dict[str, str]) -> None:
        self.title: str = title
        self.description: str = description
        self.doors: Dict[str, str] = doors
        self.visited_by_player: bool = False
        self.telium_visited_recently: bool = False
        self.entities: List[Entity] = []

    def introduce(self) -> None:
        """Introduce the module. Print the title, the description
        (if not already visited) and the doors."""
        # Title
        cprint(get_dialogue("enter_module").format(title=self.title))
        # Module description if not already seen
        if not self.visited_by_player:
            cprint(self.description)
        # Doors
        self.print_doors()

    def print_doors(self) -> None:
        """Print the doors of the module."""
        cprint("There is a door on the", end=" ")
        cprint(sent_concat(list(self.doors)), end=" ")
        cprint(f"side{'s'[:len(self.doors)^1]}.")


class Entity:
    """An entity that has a physical presence in a module."""

    def __init__(self, initial_module: ModuleInterface) -> None:
        entities.append(self)
        self.module: ModuleInterface = initial_module
        self.module.entities.append(self)
        self.previous_module: Optional[ModuleInterface] = None

    def _set_module(self, module: ModuleInterface) -> None:
        self.module.entities.remove(self)
        self.previous_module = self.module
        self.module = module
        self.module.entities.append(self)

    def on_player_entered_module(self) -> None:
        pass


class HasHealth:
    def __init__(self, initial_health: int):
        self.alive: bool = True
        self._health: int = initial_health

    def hurt(self, attack: int) -> None:
        """Decrement health by attack and check if this results in the entity dying."""
        # Prevent negative health.
        if self._health - attack > 0:
            self._health -= attack
        else:
            self._health = 0
        logger.log(
            f"{unique_name(self)} took {attack} damage, now at {self._health} health.",
            LogLevel.VERBOSE,
        )
        if self._health == 0:
            self.alive = False
            logger.log(f"{unique_name(self)} died.")


class Player(Entity, HasHealth):
    def __init__(self, initial_module: ModuleInterface) -> None:
        Entity.__init__(self, initial_module)
        HasHealth.__init__(self, 100)
        self.flamethrower_fuel: int = 100
        self.locked_module: Optional[ModuleInterface] = None

    def move_to(self, module: ModuleInterface, introduce: bool = False) -> None:
        self._set_module(module)
        if introduce:
            self.module.introduce()
        self.module.visited_by_player = True
        non_player_entities = [
            entity for entity in self.module.entities if not isinstance(entity, Player)
        ]
        module_entity_names = [unique_name(entity) for entity in non_player_entities]
        logger.log(f"Other entities in this module: {module_entity_names}")
        # Execute observers
        for entity in non_player_entities:
            logger.log(
                f"Calling on_player_entered_module of {unique_name(entity)}",
                LogLevel.VERBOSE,
            )
            entity.on_player_entered_module()
            # Player could have died in a call to on_player_entered_module so check
            if not self.alive:
                break

    def print_stats(self) -> None:
        cprint(
            f"You have {self.flamethrower_fuel} flamethrower fuel and {self._health} health."
        )


class Telium(Entity):
    ESCAPE_STEPS_RANGE = (1, 3)

    def move_to(self, module: ModuleInterface) -> None:
        self._set_module(module)
        self.module.telium_visited_recently = True

    def on_player_entered_module(self) -> None:
        escaped = False
        for _ in range(randint(*self.ESCAPE_STEPS_RANGE)):
            available_escapes: List[ModuleInterface] = []
            for module_id in self.module.doors.values():
                module = ModuleInterface(module_id)
                if (
                    module != player.previous_module
                    and module != player.module
                    and module != player.locked_module
                ):
                    available_escapes.append(module)
            if len(available_escapes) == 0:
                break
            else:
                self.move_to(choice(available_escapes))
                escaped = True
        # Describe
        if escaped:
            cprint(get_dialogue("telium_escape"))
        else:
            cprint("You are confronted by a starfish-like orange mass. It's trapped!")


class WorkerAlien(Entity, HasHealth):
    def __init__(self, initial_module: ModuleInterface) -> None:
        Entity.__init__(self, initial_module)
        HasHealth.__init__(self, randint(8, 12))
        self.attack = randint(5, 10)

    def on_player_entered_module(self) -> None:
        if self.alive:
            cprint(
                get_dialogue("worker_battle_start").format(
                    determiner="Another"
                    if any(
                        not entity.alive
                        for entity in self.module.entities
                        if isinstance(entity, WorkerAlien)
                    )
                    else "A"
                ),
                colour=Fore.YELLOW,
                character_delay=0.02,
            )
            while self.alive and player.alive:
                cprint("How much flamethrower fuel do you use against it?")
                use_fuel = int_input(">")
                if use_fuel <= player.flamethrower_fuel:
                    player.flamethrower_fuel -= use_fuel
                    self.hurt(use_fuel)
                    if not self.alive:
                        # If the player kills the alien
                        cprint(get_dialogue("worker_die"))
                        player.print_stats()
                    elif self._health <= 4:
                        # If the player wounds the alien
                        cprint(get_dialogue("worker_escape"))
                        self._set_module(random_module())
                        logger.log(f"Worker alien escaped to {self.module.title}.")
                        break
                    else:
                        # If the alien is not killed yet
                        cprint(
                            "It's not enough! The alien bites you viciously and moves to attack again."
                        )
                        player.hurt(self.attack)
                        if not player.alive:
                            cprint(get_dialogue("worker_kill_player"))
                else:
                    cprint(f"You only have {player.flamethrower_fuel} fuel.")


class SpaceStation:
    def __init__(self, modules_filename: str) -> None:
        self._energy: int = 100
        self.modules: Dict[str, Module] = {}
        with open(modules_filename, "r", encoding="utf-8") as file:
            for name, info in json.loads(file.read()).items():
                self.modules[name] = Module(
                    info["title"], info["description"], info["doors"]
                )

    def verify_modules_map(self) -> None:
        for module_id in self.modules:
            module = ModuleInterface(module_id)
            for connected_module_id in list(module.doors.values()):
                if module_id not in list(
                    ModuleInterface(connected_module_id).doors.values()
                ):
                    logger.log(
                        f"'{module_id}' is connected to '{connected_module_id}' but not vice versa",
                        LogLevel.ERROR,
                    )

    def deplete_energy(self, amount: int) -> None:
        """Deplete energy and check if this results in the station running out of energy."""
        # Prevent negative energy.
        if self._energy - amount > 0:
            self._energy -= amount
        else:
            self._energy = 0
        logger.log(
            f"{self} energy depleted by {amount}, now at {self._energy}.",
            LogLevel.VERBOSE,
        )
        if self._energy == 0:
            cprint(
                "The lights flicker and turn off. In their place, red emergency lights colours the station."
            )


# Globals
entities: List[Entity] = []

# Dialogue
dialogue: Dict[str, str] = load_dialogue(Language.ENGLISH)

# Configure
# disable_text_delay()
logger = Logger(LogLevel.VERBOSE)

# Station
station = SpaceStation(MODULES_FILE)
station.verify_modules_map()
# Entities
player = Player(random_module())
telium = Telium(random_module())
worker_aliens = [WorkerAlien(random_module()) for _ in range(NUM_WORKER_ALIENS)]

# list_available_commands([])
# Module.list_modules([])

# Introduce module, and set visited because the player did not move there
player.module.introduce()
player.module.visited_by_player = True

# Game loop
while player.alive:
    command_words = input(">").lower().split()

    if command_words:
        try:
            # Execute command, selecting by the first word of the input.
            command: Callable = available_commands[command_words[0]]
            command(command_words[1:])
        except KeyError:
            cprint('Unrecognised command, enter "commands" to list them.')
        except IndexError:
            cprint("Not enough arguments supplied. Correct usage:")
            cprint(command.__doc__, long_delay=0.02)
