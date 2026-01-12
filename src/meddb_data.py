import logging

from sqlalchemy import select, text
from sqlalchemy.orm import joinedload, aliased

from utils.config import DB_HOST, DB_USER, DB_PASS, DB_NAME, DB_SCHEMA, DB_PORT
from utils.database import DatabaseClient
from models import Base, Committee, CommitteeType, CommitteeMembership, Person, Role, Union


logger = logging.getLogger(__name__)


class MeddbData:
    """
    Class for managing MedDB data operations using SQLAlchemy ORM and DatabaseClient.
    """
    def __init__(self, db_client, schema):
        """
        Initialize the MeddbData class by setting up the database client and creating necessary schemas and tables, as well as seeding initial data.
        """
        self.db_client = db_client
        self.schema = schema

        with self.db_client.get_session() as session:
            session.execute(text(f"CREATE SCHEMA IF NOT EXISTS {self.schema}"))
            session.commit()

        # Ensure tables are created in the correct schema
        Base.metadata.create_all(self.db_client.get_engine())

        self._seed_db()

    def _seed_db(self):
        """Seed the database with initial data for committee types. if they do not already exist."""
        committee_types = [
            {"name": "Udvalg", "is_protected": True},
            {"name": "Arbejdsmiljøgruppe", "is_protected": True},
            {"name": "Ukendt", "is_protected": True},
        ]

        with self.db_client.get_session() as session:
            existing = set(
                name for (name,) in session.execute(
                    select(CommitteeType.name)
                ).all()
            )

            to_create = [CommitteeType(**ct) for ct in committee_types if ct["name"] not in existing]

            if to_create:
                session.add_all(to_create)
                session.commit()

    # GET operations
    def get_all_committee_types(self, include_protected: bool = False) -> list[CommitteeType]:
        with self.db_client.get_session() as session:
            query = session.query(CommitteeType)
            if not include_protected:
                return query.filter(CommitteeType.is_protected.is_(False)).all()
            return query.all()

    def get_all_roles(self) -> list[Role]:
        with self.db_client.get_session() as session:
            return session.query(Role).all()

    def get_all_unions(self) -> list[Union]:
        with self.db_client.get_session() as session:
            return session.query(Union).all()

    def get_union_by_id(self, union_id: int) -> Union | None:
        with self.db_client.get_session() as session:
            return session.get(Union, union_id)

    def get_persons_not_in_system(self) -> list[Person]:
        with self.db_client.get_session() as session:
            persons = (
                session.query(Person)
                .options(
                    joinedload(Person.committee_memberships).joinedload(CommitteeMembership.role)
                )
                .filter(Person.found_in_system.isnot(True))
                .all()
            )

            return persons

    def get_persons_by_roles(self, ids: list[int]) -> list[Person]:
        with self.db_client.get_session() as session:
            return (
                session.query(Person)
                .options(
                    joinedload(Person.committee_memberships).joinedload(CommitteeMembership.role)
                )
                .join(CommitteeMembership)
                .filter(CommitteeMembership.role_id.in_(ids))
                .all()
            )

    def get_persons_by_roles_and_top_committees(self, role_ids: list[int], top_committee_ids: list[int], union_ids: list[int] | None = None, in_system: bool | None = None) -> list[Person]:
        with self.db_client.get_session() as session:
            q = (
                session.query(Person)
                .options(
                    joinedload(Person.union),
                    joinedload(Person.committee_memberships).joinedload(CommitteeMembership.role),
                    joinedload(Person.committee_memberships).joinedload(CommitteeMembership.committee),
                )
                .join(Person.committee_memberships)
            )

            if in_system is not None:
                q = q.filter(Person.found_in_system == in_system)

            if union_ids:
                if None in union_ids:
                    q = q.filter(
                        (Person.union_id.in_([uid for uid in union_ids if uid is not None])) | (Person.union_id.is_(None))
                    )
                else:
                    q = q.filter(Person.union_id.in_(union_ids))

            if role_ids:
                q = q.filter(CommitteeMembership.role_id.in_(role_ids))

            if top_committee_ids:
                descendants_cte = (
                    select(Committee.id)
                    .where(Committee.id.in_(top_committee_ids))
                    .cte(name="descendants", recursive=True)
                )

                C = aliased(Committee)
                descendants_cte = descendants_cte.union_all(
                    select(C.id).where(C.parent_id == descendants_cte.c.id)
                )

                q = q.filter(
                    CommitteeMembership.committee_id.in_(select(descendants_cte.c.id))
                )

            q = q.distinct()

            return q.all()

    def get_committees(self) -> list[Committee]:
        with self.db_client.get_session() as session:
            return session.query(Committee).options(joinedload(Committee.type)).all()

    def get_committee_by_id(self, committee_id: int) -> Committee | None:
        with self.db_client.get_session() as session:
            return session.query(Committee).options(joinedload(Committee.type)).filter(Committee.id == committee_id).first()

    def get_committees_by_parent_id(self, parent_id: int) -> list[Committee]:
        with self.db_client.get_session() as session:
            return session.query(Committee).options(joinedload(Committee.type)).filter(Committee.parent_id == parent_id).all()

    def get_committee_tree(self) -> tuple[list[dict], dict[int, int | None], dict[int, dict]]:
        """Get committees structured as a tree for hierarchical representation using streamlit_tree_select."""
        committees = self.get_committees()

        node_map: dict[int, dict] = {}
        parent_map: dict[int, int | None] = {}

        for c in committees:
            node_map[c.id] = {
                "label": c.name,
                "value": c.id,
                "className": c.type.name if c.type else None,
            }
            parent_map[c.id] = c.parent_id

        roots = []
        for c in committees:
            if c.parent_id is None:
                roots.append(node_map[c.id])
            else:
                parent_node = node_map.get(c.parent_id)
                if parent_node:
                    parent_node.setdefault("children", []).append(node_map[c.id])

        def sort_nodes(nodes: list[dict]) -> list[dict]:
            """Sort nodes so that parents come before children, and alphabetically by label."""
            nodes.sort(key=lambda x: (0 if x.get("children") else 1, x["label"]))
            for node in nodes:
                children = node.get("children")
                if children:
                    sort_nodes(children)
            return nodes

        return sort_nodes(roots), parent_map, node_map

    def get_committee_members(self, committee_id: int) -> list[CommitteeMembership]:
        with self.db_client.get_session() as session:
            memberships = (
                session.query(CommitteeMembership)
                .options(
                    joinedload(CommitteeMembership.person),
                    joinedload(CommitteeMembership.role)
                )
                .filter(CommitteeMembership.committee_id == committee_id)
                .all()
            )
            return memberships

    # POST/PUT operations
    def create_role(self, name: str) -> Role:
        with self.db_client.get_session() as session:
            role = Role(name=name)
            session.add(role)
            session.commit()
            session.refresh(role)
            return role

    def create_committee_type(self, name: str) -> CommitteeType:
        with self.db_client.get_session() as session:
            committee_type = CommitteeType(name=name)
            session.add(committee_type)
            session.commit()
            session.refresh(committee_type)
            return committee_type

    def create_union(self, name: str, description: str | None) -> Union:
        with self.db_client.get_session() as session:
            union = Union(name=name, description=description)
            session.add(union)
            session.commit()
            session.refresh(union)
            return union

    def create_committee(self, name: str, type_id: int, parent_id: int | None) -> Committee:
        with self.db_client.get_session() as session:
            committee = Committee(name=name, type_id=type_id, parent_id=parent_id)
            session.add(committee)
            session.commit()
            session.refresh(committee)
            return committee

    def create_committee_member(self, committee_id: int, person_id: int, role_id: int) -> CommitteeMembership:
        with self.db_client.get_session() as session:
            membership = CommitteeMembership(
                committee_id=committee_id,
                person_id=person_id,
                role_id=role_id
            )
            session.add(membership)
            session.commit()
            session.refresh(membership)
            session.refresh(membership, attribute_names=["role"])
            return membership

    def add_or_update_person(self, name: str, email: str, found_in_system: bool = True, organization: str | None = None,
                             username: str | None = None, union_id: int | None = None) -> Person:
        with self.db_client.get_session() as session:
            person = session.query(Person).filter_by(email=email).first()
            if person:
                person.name = name
                person.found_in_system = found_in_system
                person.organization = organization if organization is not None else person.organization
                person.username = username if username is not None else person.username
                person.union_id = union_id if union_id is not None else person.union_id
                session.commit()
                session.refresh(person)
                return person
            else:
                person = Person(
                    name=name,
                    email=email,
                    found_in_system=found_in_system,
                    organization=organization,
                    username=username,
                    union_id=union_id
                )
                session.add(person)
                session.commit()
                session.refresh(person)
                return person

    # PUT/UPDATE operations
    def update_committee(self, id: int, name: str | None = None, type_id: int | None = None,
                         parent_id: int | None = False) -> Committee:
        with self.db_client.get_session() as session:
            committee = session.get(Committee, id)
            if not committee:
                raise ValueError("Committee not found.")

            if name is not None:
                committee.name = name
            if type_id is not None:
                committee.type_id = type_id
            if parent_id is not False:
                committee.parent_id = parent_id

            session.commit()
            session.refresh(committee)
            return committee

    def update_committee_type(self, id: int, name: str) -> CommitteeType:
        with self.db_client.get_session() as session:
            committee_type = session.get(CommitteeType, id)
            if not committee_type:
                raise ValueError("Committee type not found.")

            committee_type.name = name
            session.commit()
            session.refresh(committee_type)
            return committee_type

    def update_role(self, id: int, name: str) -> Role:
        with self.db_client.get_session() as session:
            role = session.get(Role, id)
            if not role:
                raise ValueError("Role not found.")

            role.name = name
            session.commit()
            session.refresh(role)
            return role

    def update_union(self, id: int, name: str, description: str | None) -> Union:
        with self.db_client.get_session() as session:
            union = session.get(Union, id)
            if not union:
                raise ValueError("Union not found.")

            union.name = name
            union.description = description
            session.commit()
            session.refresh(union)
            return union

    # DELETE operations
    def delete_committee_type(self, id: int) -> None:
        with self.db_client.get_session() as session:
            committee_type = session.get(CommitteeType, id)
            if not committee_type:
                raise ValueError("Committee type not found.")

            session.delete(committee_type)
            session.commit()

    def delete_role(self, id: int) -> None:
        with self.db_client.get_session() as session:
            role = session.get(Role, id)
            if not role:
                raise ValueError("Role not found.")

            session.delete(role)
            session.commit()

    def delete_union(self, union_id: int) -> None:
        with self.db_client.get_session() as session:
            union = session.get(Union, union_id)
            if not union:
                raise ValueError("Union not found.")

            session.delete(union)
            session.commit()

    def delete_committee_member(self, committee_id: int, person_id: int, role_id: int) -> None:
        """Delete a committee membership. Also deletes the person if they have no other memberships."""
        with self.db_client.get_session() as session:
            membership = session.query(CommitteeMembership).filter_by(
                committee_id=committee_id,
                person_id=person_id,
                role_id=role_id
            ).first()

            if not membership:
                raise ValueError("Committee membership not found.")

            session.delete(membership)
            session.flush()

            if not session.query(CommitteeMembership).filter_by(person_id=person_id).first():
                person = session.get(Person, person_id)
                if person:
                    session.delete(person)

            session.commit()

    def delete_committee(self, id: int) -> None:
        """Delete a committee and its memberships. Also deletes persons without other memberships and updates child committees to have no parent."""
        with self.db_client.get_session() as session:
            committee = session.get(Committee, id)
            if not committee:
                raise ValueError("Committee not found.")

            session.query(CommitteeMembership).filter_by(committee_id=id).delete()

            persons_without_membership = (
                session.query(Person)
                .outerjoin(CommitteeMembership, Person.id == CommitteeMembership.person_id)
                .filter(CommitteeMembership.person_id.is_(None))
                .all()
            )
            for person in persons_without_membership:
                session.delete(person)

            session.query(Committee).filter_by(parent_id=id).update({"parent_id": None})

            session.delete(committee)
            session.commit()
