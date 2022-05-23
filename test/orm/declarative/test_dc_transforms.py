import dataclasses
import inspect as pyinspect
from itertools import product
from typing import Any
from typing import List
from typing import Optional
from typing import Set
from typing import Type
from unittest import mock

from sqlalchemy import Column
from sqlalchemy import exc
from sqlalchemy import ForeignKey
from sqlalchemy import inspect
from sqlalchemy import Integer
from sqlalchemy import select
from sqlalchemy import String
from sqlalchemy import testing
from sqlalchemy.orm import column_property
from sqlalchemy.orm import composite
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import deferred
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import MappedAsDataclass
from sqlalchemy.orm import MappedColumn
from sqlalchemy.orm import registry as _RegistryType
from sqlalchemy.orm import relationship
from sqlalchemy.orm import Session
from sqlalchemy.orm import synonym
from sqlalchemy.testing import AssertsCompiledSQL
from sqlalchemy.testing import eq_
from sqlalchemy.testing import eq_regex
from sqlalchemy.testing import expect_raises
from sqlalchemy.testing import expect_raises_message
from sqlalchemy.testing import fixtures
from sqlalchemy.testing import is_false
from sqlalchemy.testing import is_true
from sqlalchemy.testing import ne_


class DCTransformsTest(AssertsCompiledSQL, fixtures.TestBase):
    def test_basic_constructor_repr_base_cls(
        self, dc_decl_base: Type[MappedAsDataclass]
    ):
        class A(dc_decl_base):
            __tablename__ = "a"

            id: Mapped[int] = mapped_column(primary_key=True, init=False)
            data: Mapped[str]

            x: Mapped[Optional[int]] = mapped_column(default=None)

            bs: Mapped[List["B"]] = relationship(  # noqa: F821
                default_factory=list
            )

        class B(dc_decl_base):
            __tablename__ = "b"

            id: Mapped[int] = mapped_column(primary_key=True, init=False)
            a_id = mapped_column(ForeignKey("a.id"), init=False)
            data: Mapped[str]
            x: Mapped[Optional[int]] = mapped_column(default=None)

        A.__qualname__ = "some_module.A"
        B.__qualname__ = "some_module.B"

        eq_(
            pyinspect.getfullargspec(A.__init__),
            pyinspect.FullArgSpec(
                args=["self", "data", "x", "bs"],
                varargs=None,
                varkw=None,
                defaults=(None, mock.ANY),
                kwonlyargs=[],
                kwonlydefaults=None,
                annotations={},
            ),
        )
        eq_(
            pyinspect.getfullargspec(B.__init__),
            pyinspect.FullArgSpec(
                args=["self", "data", "x"],
                varargs=None,
                varkw=None,
                defaults=(None,),
                kwonlyargs=[],
                kwonlydefaults=None,
                annotations={},
            ),
        )

        a2 = A("10", x=5, bs=[B("data1"), B("data2", x=12)])
        eq_(
            repr(a2),
            "some_module.A(id=None, data='10', x=5, "
            "bs=[some_module.B(id=None, data='data1', a_id=None, x=None), "
            "some_module.B(id=None, data='data2', a_id=None, x=12)])",
        )

        a3 = A("data")
        eq_(repr(a3), "some_module.A(id=None, data='data', x=None, bs=[])")

    def test_basic_constructor_repr_cls_decorator(
        self, registry: _RegistryType
    ):
        @registry.mapped_as_dataclass()
        class A:
            __tablename__ = "a"

            id: Mapped[int] = mapped_column(primary_key=True, init=False)
            data: Mapped[str]

            x: Mapped[Optional[int]] = mapped_column(default=None)

            bs: Mapped[List["B"]] = relationship(  # noqa: F821
                default_factory=list
            )

        @registry.mapped_as_dataclass()
        class B:
            __tablename__ = "b"

            id: Mapped[int] = mapped_column(primary_key=True, init=False)
            a_id = mapped_column(ForeignKey("a.id"), init=False)
            data: Mapped[str]
            x: Mapped[Optional[int]] = mapped_column(default=None)

        A.__qualname__ = "some_module.A"
        B.__qualname__ = "some_module.B"

        eq_(
            pyinspect.getfullargspec(A.__init__),
            pyinspect.FullArgSpec(
                args=["self", "data", "x", "bs"],
                varargs=None,
                varkw=None,
                defaults=(None, mock.ANY),
                kwonlyargs=[],
                kwonlydefaults=None,
                annotations={},
            ),
        )
        eq_(
            pyinspect.getfullargspec(B.__init__),
            pyinspect.FullArgSpec(
                args=["self", "data", "x"],
                varargs=None,
                varkw=None,
                defaults=(None,),
                kwonlyargs=[],
                kwonlydefaults=None,
                annotations={},
            ),
        )

        a2 = A("10", x=5, bs=[B("data1"), B("data2", x=12)])
        eq_(
            repr(a2),
            "some_module.A(id=None, data='10', x=5, "
            "bs=[some_module.B(id=None, data='data1', a_id=None, x=None), "
            "some_module.B(id=None, data='data2', a_id=None, x=12)])",
        )

        a3 = A("data")
        eq_(repr(a3), "some_module.A(id=None, data='data', x=None, bs=[])")

    def test_default_fn(self, dc_decl_base: Type[MappedAsDataclass]):
        class A(dc_decl_base):
            __tablename__ = "a"

            id: Mapped[int] = mapped_column(primary_key=True, init=False)
            data: Mapped[str] = mapped_column(default="d1")
            data2: Mapped[str] = mapped_column(default_factory=lambda: "d2")

        a1 = A()
        eq_(a1.data, "d1")
        eq_(a1.data2, "d2")

    def test_default_factory_vs_collection_class(
        self, dc_decl_base: Type[MappedAsDataclass]
    ):
        # this is currently the error raised by dataclasses.  We can instead
        # do this validation ourselves, but overall I don't know that we
        # can hit every validation and rule that's in dataclasses
        with expect_raises_message(
            ValueError, "cannot specify both default and default_factory"
        ):

            class A(dc_decl_base):
                __tablename__ = "a"

                id: Mapped[int] = mapped_column(primary_key=True, init=False)
                data: Mapped[str] = mapped_column(
                    default="d1", default_factory=lambda: "d2"
                )

    def test_inheritance(self, dc_decl_base: Type[MappedAsDataclass]):
        class Person(dc_decl_base):
            __tablename__ = "person"
            person_id: Mapped[int] = mapped_column(
                primary_key=True, init=False
            )
            name: Mapped[str]
            type: Mapped[str] = mapped_column(init=False)

            __mapper_args__ = {"polymorphic_on": type}

        class Engineer(Person):
            __tablename__ = "engineer"

            person_id: Mapped[int] = mapped_column(
                ForeignKey("person.person_id"), primary_key=True, init=False
            )

            status: Mapped[str] = mapped_column(String(30))
            engineer_name: Mapped[str]
            primary_language: Mapped[str]

        e1 = Engineer("nm", "st", "en", "pl")
        eq_(e1.name, "nm")
        eq_(e1.status, "st")
        eq_(e1.engineer_name, "en")
        eq_(e1.primary_language, "pl")

    def test_integrated_dc(self, dc_decl_base: Type[MappedAsDataclass]):
        """We will be telling users "this is a dataclass that is also
        mapped". Therefore, they will want *any* kind of attribute to do what
        it would normally do in a dataclass, including normal types without any
        field and explicit use of dataclasses.field(). additionally, we'd like
        ``Mapped`` to mean "persist this attribute". So the absence of
        ``Mapped`` should also mean something too.

        """

        class A(dc_decl_base):
            __tablename__ = "a"

            ctrl_one: str

            id: Mapped[int] = mapped_column(primary_key=True, init=False)
            data: Mapped[str]
            some_field: int = dataclasses.field(default=5)

            some_none_field: Optional[str] = None

        a1 = A("ctrlone", "datafield")
        eq_(a1.some_field, 5)
        eq_(a1.some_none_field, None)

        # only Mapped[] is mapped
        self.assert_compile(select(A), "SELECT a.id, a.data FROM a")
        eq_(
            pyinspect.getfullargspec(A.__init__),
            pyinspect.FullArgSpec(
                args=[
                    "self",
                    "ctrl_one",
                    "data",
                    "some_field",
                    "some_none_field",
                ],
                varargs=None,
                varkw=None,
                defaults=(5, None),
                kwonlyargs=[],
                kwonlydefaults=None,
                annotations={},
            ),
        )

    def test_dc_on_top_of_non_dc(self, decl_base: Type[DeclarativeBase]):
        class Person(decl_base):
            __tablename__ = "person"
            person_id: Mapped[int] = mapped_column(primary_key=True)
            name: Mapped[str]
            type: Mapped[str] = mapped_column()

            __mapper_args__ = {"polymorphic_on": type}

        class Engineer(MappedAsDataclass, Person):
            __tablename__ = "engineer"

            person_id: Mapped[int] = mapped_column(
                ForeignKey("person.person_id"), primary_key=True, init=False
            )

            status: Mapped[str] = mapped_column(String(30))
            engineer_name: Mapped[str]
            primary_language: Mapped[str]

        e1 = Engineer("st", "en", "pl")
        eq_(e1.status, "st")
        eq_(e1.engineer_name, "en")
        eq_(e1.primary_language, "pl")

        eq_(
            pyinspect.getfullargspec(Person.__init__),
            # the boring **kw __init__
            pyinspect.FullArgSpec(
                args=["self"],
                varargs=None,
                varkw="kwargs",
                defaults=None,
                kwonlyargs=[],
                kwonlydefaults=None,
                annotations={},
            ),
        )

        eq_(
            pyinspect.getfullargspec(Engineer.__init__),
            # the exciting dataclasses __init__
            pyinspect.FullArgSpec(
                args=["self", "status", "engineer_name", "primary_language"],
                varargs=None,
                varkw=None,
                defaults=None,
                kwonlyargs=[],
                kwonlydefaults=None,
                annotations={},
            ),
        )


class RelationshipDefaultFactoryTest(fixtures.TestBase):
    def test_list(self, dc_decl_base: Type[MappedAsDataclass]):
        class A(dc_decl_base):
            __tablename__ = "a"

            id: Mapped[int] = mapped_column(primary_key=True, init=False)

            bs: Mapped[List["B"]] = relationship(  # noqa: F821
                default_factory=lambda: [B(data="hi")]
            )

        class B(dc_decl_base):
            __tablename__ = "b"

            id: Mapped[int] = mapped_column(primary_key=True, init=False)
            a_id = mapped_column(ForeignKey("a.id"), init=False)
            data: Mapped[str]

        a1 = A()
        eq_(a1.bs[0].data, "hi")

    def test_set(self, dc_decl_base: Type[MappedAsDataclass]):
        class A(dc_decl_base):
            __tablename__ = "a"

            id: Mapped[int] = mapped_column(primary_key=True, init=False)

            bs: Mapped[Set["B"]] = relationship(  # noqa: F821
                default_factory=lambda: {B(data="hi")}
            )

        class B(dc_decl_base, unsafe_hash=True):
            __tablename__ = "b"

            id: Mapped[int] = mapped_column(primary_key=True, init=False)
            a_id = mapped_column(ForeignKey("a.id"), init=False)
            data: Mapped[str]

        a1 = A()
        eq_(a1.bs.pop().data, "hi")

    def test_oh_no_mismatch(self, dc_decl_base: Type[MappedAsDataclass]):
        class A(dc_decl_base):
            __tablename__ = "a"

            id: Mapped[int] = mapped_column(primary_key=True, init=False)

            bs: Mapped[Set["B"]] = relationship(  # noqa: F821
                default_factory=lambda: [B(data="hi")]
            )

        class B(dc_decl_base, unsafe_hash=True):
            __tablename__ = "b"

            id: Mapped[int] = mapped_column(primary_key=True, init=False)
            a_id = mapped_column(ForeignKey("a.id"), init=False)
            data: Mapped[str]

        # old school collection mismatch error FTW
        with expect_raises_message(
            TypeError, "Incompatible collection type: list is not set-like"
        ):
            A()

    def test_replace_operation_works_w_history_etc(
        self, registry: _RegistryType
    ):
        @registry.mapped_as_dataclass
        class A:
            __tablename__ = "a"

            id: Mapped[int] = mapped_column(primary_key=True, init=False)
            data: Mapped[str]

            x: Mapped[Optional[int]] = mapped_column(default=None)

            bs: Mapped[List["B"]] = relationship(  # noqa: F821
                default_factory=list
            )

        @registry.mapped_as_dataclass
        class B:
            __tablename__ = "b"

            id: Mapped[int] = mapped_column(primary_key=True, init=False)
            a_id = mapped_column(ForeignKey("a.id"), init=False)
            data: Mapped[str]
            x: Mapped[Optional[int]] = mapped_column(default=None)

        registry.metadata.create_all(testing.db)

        with Session(testing.db) as sess:
            a1 = A("data", 10, [B("b1"), B("b2", x=5), B("b3")])
            sess.add(a1)
            sess.commit()

            a2 = dataclasses.replace(a1, x=12, bs=[B("b4")])

            assert a1 in sess
            assert not sess.is_modified(a1, include_collections=True)
            assert a2 not in sess
            eq_(inspect(a2).attrs.x.history, ([12], (), ()))
            sess.add(a2)
            sess.commit()

            eq_(sess.scalars(select(A.x).order_by(A.id)).all(), [10, 12])
            eq_(
                sess.scalars(select(B.data).order_by(B.id)).all(),
                ["b1", "b2", "b3", "b4"],
            )

    def test_post_init(self, registry: _RegistryType):
        @registry.mapped_as_dataclass
        class A:
            __tablename__ = "a"

            id: Mapped[int] = mapped_column(primary_key=True, init=False)
            data: Mapped[str] = mapped_column(init=False)

            def __post_init__(self):
                self.data = "some data"

        a1 = A()
        eq_(a1.data, "some data")

    def test_no_field_args_w_new_style(self, registry: _RegistryType):
        with expect_raises_message(
            exc.InvalidRequestError,
            "SQLAlchemy mapped dataclasses can't consume mapping information",
        ):

            @registry.mapped_as_dataclass()
            class A:
                __tablename__ = "a"
                __sa_dataclass_metadata_key__ = "sa"

                account_id: int = dataclasses.field(
                    init=False,
                    metadata={"sa": Column(Integer, primary_key=True)},
                )

    def test_no_field_args_w_new_style_two(self, registry: _RegistryType):
        @dataclasses.dataclass
        class Base:
            pass

        with expect_raises_message(
            exc.InvalidRequestError,
            "SQLAlchemy mapped dataclasses can't consume mapping information",
        ):

            @registry.mapped_as_dataclass()
            class A(Base):
                __tablename__ = "a"
                __sa_dataclass_metadata_key__ = "sa"

                account_id: int = dataclasses.field(
                    init=False,
                    metadata={"sa": Column(Integer, primary_key=True)},
                )


class DataclassArgsTest(fixtures.TestBase):
    dc_arg_names = ("init", "repr", "eq", "order", "unsafe_hash")

    @testing.fixture(params=product(dc_arg_names, (True, False)))
    def dc_argument_fixture(self, request: Any, registry: _RegistryType):
        name, use_defaults = request.param

        args = {n: n == name for n in self.dc_arg_names}
        if args["order"]:
            args["eq"] = True
        if use_defaults:
            default = {
                "init": True,
                "repr": True,
                "eq": True,
                "order": False,
                "unsafe_hash": False,
            }
            to_apply = {k: v for k, v in args.items() if v}
            effective = {**default, **to_apply}
            return to_apply, effective
        else:
            return args, args

    @testing.fixture(
        params=["mapped_column", "synonym", "deferred", "column_property"]
    )
    def mapped_expr_constructor(self, request):
        name = request.param

        if name == "mapped_column":
            yield mapped_column(default=7, init=True)
        elif name == "synonym":
            yield synonym("some_int", default=7, init=True)
        elif name == "deferred":
            yield deferred(Column(Integer), default=7, init=True)
        elif name == "column_property":
            yield column_property(Column(Integer), default=7, init=True)

    def test_attrs_rejected_if_not_a_dc(
        self, mapped_expr_constructor, decl_base: Type[DeclarativeBase]
    ):
        if isinstance(mapped_expr_constructor, MappedColumn):
            unwanted_args = "'init'"
        else:
            unwanted_args = "'default', 'init'"
        with expect_raises_message(
            exc.ArgumentError,
            r"Attribute 'x' on class .*A.* includes dataclasses "
            r"argument\(s\): "
            rf"{unwanted_args} but class does not specify SQLAlchemy native "
            "dataclass configuration",
        ):

            class A(decl_base):
                __tablename__ = "a"

                id: Mapped[int] = mapped_column(primary_key=True)

                x: Mapped[int] = mapped_expr_constructor

    def _assert_cls(self, cls, dc_arguments):

        if dc_arguments["init"]:

            def create(data, x):
                return cls(data, x)

        else:

            def create(data, x):
                a1 = cls()
                a1.data = data
                a1.x = x
                return a1

        for n in self.dc_arg_names:
            if dc_arguments[n]:
                getattr(self, f"_assert_{n}")(cls, create, dc_arguments)
            else:
                getattr(self, f"_assert_not_{n}")(cls, create, dc_arguments)

            if dc_arguments["init"]:
                a1 = cls("some data")
                eq_(a1.x, 7)

        a1 = create("some data", 15)
        some_int = a1.some_int
        eq_(
            dataclasses.asdict(a1),
            {"data": "some data", "id": None, "some_int": some_int, "x": 15},
        )
        eq_(dataclasses.astuple(a1), (None, "some data", some_int, 15))

    def _assert_unsafe_hash(self, cls, create, dc_arguments):
        a1 = create("d1", 5)
        hash(a1)

    def _assert_not_unsafe_hash(self, cls, create, dc_arguments):
        a1 = create("d1", 5)

        if dc_arguments["eq"]:
            with expect_raises(TypeError):
                hash(a1)
        else:
            hash(a1)

    def _assert_eq(self, cls, create, dc_arguments):
        a1 = create("d1", 5)
        a2 = create("d2", 10)
        a3 = create("d1", 5)

        eq_(a1, a3)
        ne_(a1, a2)

    def _assert_not_eq(self, cls, create, dc_arguments):
        a1 = create("d1", 5)
        a2 = create("d2", 10)
        a3 = create("d1", 5)

        eq_(a1, a1)
        ne_(a1, a3)
        ne_(a1, a2)

    def _assert_order(self, cls, create, dc_arguments):
        is_false(create("g", 10) < create("b", 7))

        is_true(create("g", 10) > create("b", 7))

        is_false(create("g", 10) <= create("b", 7))

        is_true(create("g", 10) >= create("b", 7))

        eq_(
            list(sorted([create("g", 10), create("g", 5), create("b", 7)])),
            [
                create("b", 7),
                create("g", 5),
                create("g", 10),
            ],
        )

    def _assert_not_order(self, cls, create, dc_arguments):
        with expect_raises(TypeError):
            create("g", 10) < create("b", 7)

        with expect_raises(TypeError):
            create("g", 10) > create("b", 7)

        with expect_raises(TypeError):
            create("g", 10) <= create("b", 7)

        with expect_raises(TypeError):
            create("g", 10) >= create("b", 7)

    def _assert_repr(self, cls, create, dc_arguments):
        a1 = create("some data", 12)
        eq_regex(repr(a1), r".*A\(id=None, data='some data', x=12\)")

    def _assert_not_repr(self, cls, create, dc_arguments):
        a1 = create("some data", 12)
        eq_regex(repr(a1), r"<.*A object at 0x.*>")

    def _assert_init(self, cls, create, dc_arguments):
        a1 = cls("some data", 5)

        eq_(a1.data, "some data")
        eq_(a1.x, 5)

        a2 = cls(data="some data", x=5)
        eq_(a2.data, "some data")
        eq_(a2.x, 5)

        a3 = cls(data="some data")
        eq_(a3.data, "some data")
        eq_(a3.x, 7)

    def _assert_not_init(self, cls, create, dc_arguments):

        with expect_raises(TypeError):
            cls("Some data", 5)

        # we run real "dataclasses" on the class.  so with init=False, it
        # doesn't touch what was there, and the SQLA default constructor
        # gets put on.
        a1 = cls(data="some data")
        eq_(a1.data, "some data")
        eq_(a1.x, None)

        a1 = cls()
        eq_(a1.data, None)

        # no constructor, it sets None for x...ok
        eq_(a1.x, None)

    def test_dc_arguments_decorator(
        self,
        dc_argument_fixture,
        mapped_expr_constructor,
        registry: _RegistryType,
    ):
        @registry.mapped_as_dataclass(**dc_argument_fixture[0])
        class A:
            __tablename__ = "a"

            id: Mapped[int] = mapped_column(primary_key=True, init=False)
            data: Mapped[str]

            some_int: Mapped[int] = mapped_column(init=False, repr=False)

            x: Mapped[Optional[int]] = mapped_expr_constructor

        self._assert_cls(A, dc_argument_fixture[1])

    def test_dc_arguments_base(
        self,
        dc_argument_fixture,
        mapped_expr_constructor,
        registry: _RegistryType,
    ):
        reg = registry

        class Base(
            MappedAsDataclass, DeclarativeBase, **dc_argument_fixture[0]
        ):
            registry = reg

        class A(Base):
            __tablename__ = "a"

            id: Mapped[int] = mapped_column(primary_key=True, init=False)
            data: Mapped[str]

            some_int: Mapped[int] = mapped_column(init=False, repr=False)

            x: Mapped[Optional[int]] = mapped_expr_constructor

        self._assert_cls(A, dc_argument_fixture[1])

    def test_dc_arguments_perclass(
        self,
        dc_argument_fixture,
        mapped_expr_constructor,
        decl_base: Type[DeclarativeBase],
    ):
        class A(MappedAsDataclass, decl_base, **dc_argument_fixture[0]):
            __tablename__ = "a"

            id: Mapped[int] = mapped_column(primary_key=True, init=False)
            data: Mapped[str]

            some_int: Mapped[int] = mapped_column(init=False, repr=False)

            x: Mapped[Optional[int]] = mapped_expr_constructor

        self._assert_cls(A, dc_argument_fixture[1])

    def test_dc_arguments_override_base(self, registry: _RegistryType):
        reg = registry

        class Base(MappedAsDataclass, DeclarativeBase, init=False, order=True):
            registry = reg

        class A(Base, init=True, repr=False):
            __tablename__ = "a"

            id: Mapped[int] = mapped_column(primary_key=True, init=False)
            data: Mapped[str]

            some_int: Mapped[int] = mapped_column(init=False, repr=False)

            x: Mapped[Optional[int]] = mapped_column(default=7)

        effective = {
            "init": True,
            "repr": False,
            "eq": True,
            "order": True,
            "unsafe_hash": False,
        }
        self._assert_cls(A, effective)

    def test_dc_base_unsupported_argument(self, registry: _RegistryType):
        reg = registry
        with expect_raises(TypeError):

            class Base(MappedAsDataclass, DeclarativeBase, slots=True):
                registry = reg

        class Base2(MappedAsDataclass, DeclarativeBase, order=True):
            registry = reg

        with expect_raises(TypeError):

            class A(Base2, slots=False):
                __tablename__ = "a"

                id: Mapped[int] = mapped_column(primary_key=True, init=False)

    def test_dc_decorator_unsupported_argument(self, registry: _RegistryType):
        reg = registry
        with expect_raises(TypeError):

            @registry.mapped_as_dataclass(slots=True)
            class Base(DeclarativeBase):
                registry = reg

        class Base2(MappedAsDataclass, DeclarativeBase, order=True):
            registry = reg

        with expect_raises(TypeError):

            @registry.mapped_as_dataclass(slots=True)
            class A(Base2):
                __tablename__ = "a"

                id: Mapped[int] = mapped_column(primary_key=True, init=False)

    def test_dc_raise_for_slots(
        self,
        registry: _RegistryType,
        decl_base: Type[DeclarativeBase],
    ):
        reg = registry
        with expect_raises_message(
            exc.ArgumentError,
            r"Dataclass argument\(s\) 'slots', 'unknown' are not accepted",
        ):

            class A(MappedAsDataclass, decl_base):
                __tablename__ = "a"
                _sa_apply_dc_transforms = {"slots": True, "unknown": 5}

                id: Mapped[int] = mapped_column(primary_key=True, init=False)

        with expect_raises_message(
            exc.ArgumentError,
            r"Dataclass argument\(s\) 'slots' are not accepted",
        ):

            class Base(MappedAsDataclass, DeclarativeBase, order=True):
                registry = reg
                _sa_apply_dc_transforms = {"slots": True}

        with expect_raises_message(
            exc.ArgumentError,
            r"Dataclass argument\(s\) 'slots', 'unknown' are not accepted",
        ):

            @reg.mapped
            class C:
                __tablename__ = "a"
                _sa_apply_dc_transforms = {"slots": True, "unknown": 5}

                id: Mapped[int] = mapped_column(primary_key=True, init=False)


class CompositeTest(fixtures.TestBase, testing.AssertsCompiledSQL):
    __dialect__ = "default"

    def test_composite_setup(self, dc_decl_base: Type[MappedAsDataclass]):
        @dataclasses.dataclass
        class Point:
            x: int
            y: int

        class Edge(dc_decl_base):
            __tablename__ = "edge"
            id: Mapped[int] = mapped_column(primary_key=True, init=False)
            graph_id: Mapped[int] = mapped_column(
                ForeignKey("graph.id"), init=False
            )

            start: Mapped[Point] = composite(
                Point, mapped_column("x1"), mapped_column("y1"), default=None
            )

            end: Mapped[Point] = composite(
                Point, mapped_column("x2"), mapped_column("y2"), default=None
            )

        class Graph(dc_decl_base):
            __tablename__ = "graph"
            id: Mapped[int] = mapped_column(primary_key=True, init=False)

            edges: Mapped[List[Edge]] = relationship()

        Point.__qualname__ = "mymodel.Point"
        Edge.__qualname__ = "mymodel.Edge"
        Graph.__qualname__ = "mymodel.Graph"
        g = Graph(
            edges=[
                Edge(start=Point(1, 2), end=Point(3, 4)),
                Edge(start=Point(7, 8), end=Point(5, 6)),
            ]
        )
        eq_(
            repr(g),
            "mymodel.Graph(id=None, edges=[mymodel.Edge(id=None, "
            "graph_id=None, start=mymodel.Point(x=1, y=2), "
            "end=mymodel.Point(x=3, y=4)), "
            "mymodel.Edge(id=None, graph_id=None, "
            "start=mymodel.Point(x=7, y=8), end=mymodel.Point(x=5, y=6))])",
        )

    def test_named_setup(self, dc_decl_base: Type[MappedAsDataclass]):
        @dataclasses.dataclass
        class Address:
            street: str
            state: str
            zip_: str

        class User(dc_decl_base):
            __tablename__ = "user"

            id: Mapped[int] = mapped_column(
                primary_key=True, init=False, repr=False
            )
            name: Mapped[str] = mapped_column()

            address: Mapped[Address] = composite(
                Address,
                mapped_column(),
                mapped_column(),
                mapped_column("zip"),
                default=None,
            )

        Address.__qualname__ = "mymodule.Address"
        User.__qualname__ = "mymodule.User"
        u = User(
            name="user 1",
            address=Address("123 anywhere street", "NY", "12345"),
        )
        u2 = User("u2")
        eq_(
            repr(u),
            "mymodule.User(name='user 1', "
            "address=mymodule.Address(street='123 anywhere street', "
            "state='NY', zip_='12345'))",
        )
        eq_(repr(u2), "mymodule.User(name='u2', address=None)")
