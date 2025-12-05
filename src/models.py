
from sqlalchemy import Integer, Unicode, ForeignKey, PrimaryKeyConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from utils.config import DB_SCHEMA


class Base(DeclarativeBase):
    pass


class CommitteeType(Base):
    __tablename__ = "committee_type"
    __table_args__ = {"schema": DB_SCHEMA}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Unicode(100), unique=True, nullable=False)
    is_protected: Mapped[bool] = mapped_column(default=False, nullable=False)

    committees: Mapped[list["Committee"]] = relationship(back_populates="type")


class Committee(Base):
    __tablename__ = "committee"
    __table_args__ = {"schema": DB_SCHEMA}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Unicode(100), nullable=False)
    type_id: Mapped[int] = mapped_column(ForeignKey(f"{DB_SCHEMA}.committee_type.id"))
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey(f"{DB_SCHEMA}.committee.id", ondelete="SET NULL"), nullable=True
    )

    type: Mapped["CommitteeType"] = relationship(back_populates="committees")
    parent: Mapped["Committee | None"] = relationship(remote_side=[id])
    committee_memberships: Mapped[list["CommitteeMembership"]] = relationship(back_populates="committee")


class Union(Base):
    __tablename__ = "union"
    __table_args__ = {"schema": DB_SCHEMA}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Unicode(100), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Unicode(255), nullable=True)

    persons: Mapped[list["Person"]] = relationship(back_populates="union")


class Person(Base):
    __tablename__ = "person"
    __table_args__ = {"schema": DB_SCHEMA}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(Unicode(100), nullable=True)
    name: Mapped[str] = mapped_column(Unicode(255), nullable=False)
    email: Mapped[str | None] = mapped_column(Unicode(255), unique=True, nullable=False)
    organization: Mapped[str | None] = mapped_column(Unicode(100), nullable=True)
    found_in_system: Mapped[bool] = mapped_column(default=False)

    union_id: Mapped[int | None] = mapped_column(
        ForeignKey(f"{DB_SCHEMA}.union.id", ondelete="SET NULL"), nullable=True
    )

    union: Mapped["Union | None"] = relationship(back_populates="persons")
    committee_memberships: Mapped[list["CommitteeMembership"]] = relationship(back_populates="person")


class Role(Base):
    __tablename__ = "role"
    __table_args__ = {"schema": DB_SCHEMA}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Unicode(100), unique=True, nullable=False)

    committee_memberships: Mapped[list["CommitteeMembership"]] = relationship(back_populates="role")


class CommitteeMembership (Base):
    __tablename__ = "committee_membership"
    __table_args__ = (
        PrimaryKeyConstraint("person_id", "role_id", "committee_id"),
        {"schema": DB_SCHEMA}
    )
    # id: Mapped[int] = mapped_column(Integer, primary_key=True)
    person_id: Mapped[int] = mapped_column(ForeignKey(f"{DB_SCHEMA}.person.id"))
    role_id: Mapped[int] = mapped_column(ForeignKey(f"{DB_SCHEMA}.role.id"))
    committee_id: Mapped[int] = mapped_column(ForeignKey(f"{DB_SCHEMA}.committee.id"))

    person: Mapped["Person"] = relationship(back_populates="committee_memberships")
    role: Mapped["Role"] = relationship(back_populates="committee_memberships")
    committee: Mapped["Committee"] = relationship(back_populates="committee_memberships")
