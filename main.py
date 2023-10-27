from typing import Dict, List, Callable
from random import choice, randint
import json
from colorama import Fore, Back, Style

from utils import *

# Constants
MODULES_FILENAME = "space_modules.json"
DIRECTIONS = [
    "north",
    "northeast",
    "east",
    "southeast",
    "south",
    "southwest",
    "west",
    "northwest",
]
DIRECTION_ALIASES = {
    "n": "north",
    "ne": "northeast",
    "e": "east",
    "se": "southeast",
    "s": "south",
    "sw": "southwest",
    "w": "west",
    "nw": "northwest",
}
# Gameplay constants
NUM_WORKER_ALIENS = 4
LOCK_MODULE_ENERGY = 20

# Available commands handling
available_commands: Dict[str, Callable] = {}
command_helps: List[str] = []


def command(word: str):
    """Register a command."""

    def wrap(func: Callable):
        available_commands[word] = func
        if func.__doc__ is not None:
            command_helps.append(func.__doc__)
        return func

    return wrap


@command("quit")
def quit_game(_):
    """quit: Quit the game."""
    if yes_or_no("Are you sure you want to quit? Your progress will be lost."):
        quit()
    else:
        cprint("Quit cancelled.")


@command("commands")
def list_available_commands(_):
    """commands: List the available commands."""
    cprint("You can use these commands:")
    for command_help in command_helps:
        cprint(" - " + command_help, long_delay=0.02)


@command("doors")
def print_doors(_):
    """doors: List the available doors."""
    player.module.print_doors()


@command("debug")
def debug(_):
    breakpoint()


class ModuleInterface(object):
    """Allows referencing a module directly instead of by indexing the global
    list of modules. Raises an assertion error if it is attempted to be created
    for a module that does not exist."""

    def __init__(self, module_id):
        assert module_id in list(station.modules.keys())
        object.__setattr__(self, "module_id", module_id)

    def __getattribute__(self, name):
        return station.modules[
            object.__getattribute__(self, "module_id")
        ].__getattribute__(name)

    def __setattr__(self, name, value):
        station.modules[object.__getattribute__(self, "module_id")].__setattr__(
            name, value
        )

    def __eq__(self, other):
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

    def __ne__(self, other):
        return not self == other


class Module:
    """Space station module."""

    d_enter = Dialogue(
        "You find yourself in the {title}.",
        "You step into the {title}.",
        "You cautiously enter the {title}.",
    )

    def __init__(self, title, description, doors):
        self.title: str = title
        self.description: str = description
        self.doors: Dict[str, str] = doors
        self.visited_by_player = False
        self.telium_visited_recently = False
        self.entities: List[Entity] = []

    def introduce(self):
        """Introduce the module. Print the title, the description
        (if not already visited) and the doors."""
        # Title
        cprint(self.d_enter.format(title=self.title))
        # Module description if not already seen
        if not self.visited_by_player:
            cprint(self.description)
        # Doors
        self.print_doors()

    def print_doors(self):
        """Print the doors of the module."""
        cprint("There is a door on the", end=" ")
        cprint(sent_concat(list(self.doors)), end=" ")
        cprint(f"side{'s'[:len(self.doors)^1]}.")

    def random(exclude: List[ModuleInterface] = []) -> ModuleInterface:
        """Return a random module, optionally excluding some of them."""
        return ModuleInterface(
            choice(
                list(
                    filter(
                        lambda mid: not ModuleInterface(mid) in exclude,
                        station.modules.keys(),
                    )
                )
            )
        )

    @command("modules")
    def list_modules(_):
        """modules: List the modules in the station."""
        cprint("These modules are in the station:")
        for module_id in station.modules:
            module = ModuleInterface(module_id)
            cprint(f" - {module.title} ({module_id})")


class Entity:
    """An entity that has a physical presence in a module."""

    def __init__(self, initial_module):
        entities.append(self)
        self.module: ModuleInterface = initial_module
        self.module.entities.append(self)
        self.previous_module: ModuleInterface = None

    def _set_module(self, module: ModuleInterface):
        self.module.entities.remove(self)
        self.previous_module = self.module
        self.module = module
        self.module.entities.append(self)

    def on_player_entered_module(self):
        pass


class Hurtable:
    def __init__(self, initial_health):
        self.alive = True
        self._health = initial_health

    def hurt(self, attack: int):
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


class Player(Entity, Hurtable):
    """Player singleton."""

    def __init__(self, initial_module):
        Entity.__init__(self, initial_module)
        Hurtable.__init__(self, 100)
        self.flamethrower_fuel = 100
        self.locked_module: ModuleInterface = None

    def move_to(self, module: ModuleInterface, introduce=False):
        """Move the player to a given module and record that they have
        visited. Optionally also introduce the module moved to."""
        self._set_module(module)
        if introduce:
            self.module.introduce()
        self.module.visited_by_player = True
        logger.log(
            f"Other entities in this module: {[unique_name(entity) for entity in list(filter(lambda entity: not isinstance(entity, Player), self.module.entities))]}"
        )
        # Execute observers
        for entity in list(
            filter(lambda entity: not isinstance(entity, Player), self.module.entities)
        ):
            logger.log(
                f"Calling on_player_entered_module of {unique_name(entity)}",
                LogLevel.VERBOSE,
            )
            entity.on_player_entered_module()
            # Player could have died in a call to on_player_entered_module so check
            if not self.alive:
                break

    def print_stats(self):
        cprint(
            f"You have {self.flamethrower_fuel} flamethrower fuel and {self._health} health."
        )

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
            player.move_to(
                ModuleInterface(player.module.doors[direction]), introduce=True
            )
            return True
        except KeyError:
            cprint("You bump into the wall.")
            player.module.print_doors()
            return False

    # TODO: don't lock already locked
    # TODO: energy stuff

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
    def stats(_):
        """stats: Show your current stats."""
        player.print_stats()


class Telium(Entity):
    d_escape = Dialogue(
        "In the corner of your eye you see an orange blob disappear through a door.",
        "As you enter, another door is just closing.",
        "You spot a flash of orange in your peripheral vision.",
    )

    ESCAPE_STEPS_RANGE = (1, 3)

    def move_to(self, module: ModuleInterface):
        self._set_module(module)
        self.module.telium_visited_recently = True

    def on_player_entered_module(self):
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
            cprint(self.d_escape)
        else:
            cprint("You are confronted by a starfish-like orange mass. It's trapped!")


class WorkerAlien(Entity, Hurtable):
    d_battle_start = Dialogue(
        "{determiner} small orange alien scuttles across the floor and leaps towards you!",
        "{determiner} small orange alien jumps out from behind a crate!",
        "{determiner} small orange alien falls from the ceiling towards you!",
    )
    d_die = Dialogue(
        "The alien falls lifeless to the floor, smouldering.",
        "The alien lies charred on the floor.",
        "The alien is blasted into a corner and stops moving.",
    )
    d_player_kill = Dialogue(
        "The alien chews off your leg and you die.", "The alien kills you to death."
    )
    d_escape = Dialogue(
        "Wounded, the alien disappears into a vent, escaping to another module."
    )

    def __init__(self, initial_module):
        Entity.__init__(self, initial_module)
        Hurtable.__init__(self, randint(8, 12))
        self.attack = randint(5, 10)

    def on_player_entered_module(self):
        if self.alive:
            cprint(
                self.d_battle_start.format(
                    determiner="Another"
                    if any(
                        not e.alive
                        for e in filter(
                            lambda e: isinstance(e, WorkerAlien), self.module.entities
                        )
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
                        cprint(self.d_die)
                        player.print_stats()
                    elif self._health <= 4:
                        # If the player wounds the alien
                        cprint(self.d_escape)
                        self._set_module(Module.random([self.module]))
                        logger.log(f"Worker alien escaped to {self.module.title}.")
                        break
                    else:
                        # If the alien is not killed yet
                        cprint(
                            "It's not enough! The alien bites you viciously and moves to attack again."
                        )
                        player.hurt(self.attack)
                        if not player.alive:
                            cprint(self.d_player_kill)
                else:
                    cprint(f"You only have {player.flamethrower_fuel} fuel.")


class SpaceStation:
    def __init__(self, modules_filename):
        self._energy = 100
        self.modules: Dict[str, Module] = {}
        with open(modules_filename, "r", encoding="utf-8") as file:
            for name, info in json.loads(file.read()).items():
                self.modules[name] = Module(
                    info["title"], info["description"], info["doors"]
                )

    def verify_modules_map(self):
        for module_id in self.modules:
            module = ModuleInterface(module_id)
            for connected_module_id in list(module.doors.values()):
                if not module_id in list(
                    ModuleInterface(connected_module_id).doors.values()
                ):
                    logger.log(
                        f"'{module_id}' is connected to '{connected_module_id}' but not vice versa",
                        LogLevel.ERROR,
                    )

    def deplete_energy(self, amount: int):
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

# Configure
# disable_text_delay()
logger = Logger(LogLevel.VERBOSE)

# Station
station = SpaceStation(MODULES_FILENAME)
station.verify_modules_map()
# Entities
player = Player(Module.random())
telium = Telium(Module.random([player.module]))
worker_aliens = [
    WorkerAlien(Module.random([player.module])) for _ in range(NUM_WORKER_ALIENS)
]

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
