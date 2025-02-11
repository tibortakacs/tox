from __future__ import annotations

from abc import abstractmethod
from argparse import ArgumentTypeError
from typing import TYPE_CHECKING, Any, List, Mapping, TypeVar

from tox.plugin import impl

from .convert import Convert, Factory
from .section import Section
from .str_convert import StrConvert

if TYPE_CHECKING:
    from tox.config.cli.parser import ToxParser
    from tox.config.main import Config


class Override:
    """
    An override for config definitions.
    """

    def __init__(self, value: str) -> None:
        key, equal, self.value = value.partition("=")
        if not equal:
            raise ArgumentTypeError(f"override {value} has no = sign in it")
        self.namespace, _, self.key = key.rpartition(".")

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}('{self}')"

    def __str__(self) -> str:
        return f"{self.namespace}{'.' if self.namespace else ''}{self.key}={self.value}"

    def __eq__(self, other: Any) -> bool:
        if type(self) != type(other):
            return False
        return (self.namespace, self.key, self.value) == (other.namespace, other.key, other.value)

    def __ne__(self, other: Any) -> bool:
        return not (self == other)


class ConfigLoadArgs:
    """Arguments that help loading a configuration value."""

    def __init__(self, chain: list[str] | None, name: str | None, env_name: str | None):
        """
        :param chain: the configuration chain (useful to detect circular references)
        :param name: the name of the configuration
        :param env_name: the tox environment this load is for
        """
        self.chain: list[str] = chain or []
        self.name = name
        self.env_name = env_name

    def copy(self) -> ConfigLoadArgs:
        """:return: create a copy of the object"""
        return ConfigLoadArgs(self.chain.copy(), self.name, self.env_name)


OverrideMap = Mapping[str, List[Override]]

T = TypeVar("T")
V = TypeVar("V")


class Loader(Convert[T]):
    """Loader loads a configuration value and converts it."""

    def __init__(self, section: Section, overrides: list[Override]) -> None:
        self._section = section
        self.overrides = {o.key: o for o in overrides}
        self.parent: Loader[Any] | None = None

    @property
    def section(self) -> Section:
        return self._section

    @abstractmethod
    def load_raw(self, key: str, conf: Config | None, env_name: str | None) -> T:
        """
        Load the raw object from the config store.

        :param key: the key under what we want the configuration
        :param env_name: load for env name
        :param conf: the global config object
        """
        raise NotImplementedError

    @abstractmethod
    def found_keys(self) -> set[str]:
        """A list of configuration keys found within the configuration."""
        raise NotImplementedError

    def __repr__(self) -> str:
        return f"{type(self).__name__}"

    def __contains__(self, item: str) -> bool:
        return item in self.found_keys()

    def load(
        self,
        key: str,
        of_type: type[V],
        factory: Factory[V],
        conf: Config | None,
        args: ConfigLoadArgs,
    ) -> V:
        """
        Load a value (raw and then convert).

        :param key: the key under it lives
        :param of_type: the type to convert to
        :param factory: factory method to build the object
        :param conf: the configuration object of this tox session (needed to manifest the value)
        :param args: the config load arguments
        :return: the converted type
        """
        if key in self.overrides:
            return _STR_CONVERT.to(self.overrides[key].value, of_type, factory)
        raw = self.load_raw(key, conf, args.env_name)
        return self.build(key, of_type, factory, conf, raw, args)

    def build(
        self,
        key: str,  # noqa: U100
        of_type: type[V],
        factory: Factory[V],
        conf: Config | None,  # noqa: U100
        raw: T,
        args: ConfigLoadArgs,  # noqa: U100
    ) -> V:
        """
        Materialize the raw configuration value from the loader.

        :param future: a future which when called will provide the converted config value
        :param key: the config key
        :param of_type: the config type
        :param conf: the global config
        :param raw: the raw value
        :param args: env args
        """
        return self.to(raw, of_type, factory)


@impl
def tox_add_option(parser: ToxParser) -> None:
    parser.add_argument(
        "-x",
        "--override",
        action="append",
        type=Override,
        default=[],
        dest="override",
        help="configuration override(s)",
    )


_STR_CONVERT = StrConvert()
