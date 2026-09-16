"""Guards on the MongoDB behaviour this app depends on.

No real mongod is reachable in CI, so correctness is defended two ways:

1. The indexes production creates are actually built in tests (see conftest),
   so constraints such as the unique users.email are genuinely enforced.
2. Every query shape the app issues is run against two independent engines --
   mongomock and montydb -- and asserted to agree. Two separate implementations
   returning the same rows is meaningful evidence the query means what we think.

What this cannot cover: server-side behaviour with no Python implementation,
notably $text search scoring and real concurrency. Those still need one pass
against a real mongod before production.
"""
import tempfile

import pytest
from pymongo.errors import DuplicateKeyError

from app.routers.leads import build_lead_query

pytestmark = pytest.mark.asyncio

montydb = pytest.importorskip("montydb", reason="montydb provides the second engine")


SAMPLE = [
    {"name": "Warung Kopi Senja", "region": "jakarta_selatan", "score": 34, "status": "new"},
    {"name": "Butik Hijab Amara", "region": "bogor", "score": 90, "status": "contacted"},
    {"name": "Bengkel Motor Jaya", "region": "depok", "score": 27, "status": "new"},
    {"name": "Katering Dapur Ibu", "region": "bekasi", "score": 61, "status": "qualified"},
]

# The query shapes the lead dashboard, export and admin screens actually issue.
QUERIES = [
    {},
    {"region": "bogor"},
    {"status": "new"},
    {"score": {"$gte": 0, "$lte": 40}},
    {"score": {"$gte": 60}},
    {"region": {"$in": ["bogor", "depok"]}},
    {"$or": [
        {"name": {"$regex": "Kopi", "$options": "i"}},
        {"region": {"$regex": "bogor", "$options": "i"}},
    ]},
    {"$or": [{"name": {"$regex": "tidak-ada", "$options": "i"}}], "status": "new"},
    {"status": "new", "score": {"$lte": 30}},
]


def _monty_collection():
    tmp = tempfile.mkdtemp()
    montydb.set_storage(tmp, storage="sqlite")
    col = montydb.MontyClient(tmp)["contract"]["leads"]
    col.insert_many([dict(doc) for doc in SAMPLE])
    return col


class TestQueryEnginesAgree:
    @pytest.mark.parametrize("query", QUERIES)
    async def test_same_documents_from_both_engines(self, query, mock_db):
        await mock_db.contract_leads.insert_many([dict(doc) for doc in SAMPLE])
        mock_names = sorted(
            doc["name"] for doc in await mock_db.contract_leads.find(query).to_list(50)
        )
        monty_names = sorted(doc["name"] for doc in _monty_collection().find(query))
        assert mock_names == monty_names, f"engines disagree for {query}"

    @pytest.mark.parametrize("query", QUERIES)
    async def test_same_counts_from_both_engines(self, query, mock_db):
        await mock_db.contract_leads.insert_many([dict(doc) for doc in SAMPLE])
        assert await mock_db.contract_leads.count_documents(query) == _monty_collection().count_documents(query)

    async def test_sort_skip_limit_agree(self, mock_db):
        await mock_db.contract_leads.insert_many([dict(doc) for doc in SAMPLE])
        mock_page = [
            doc["name"]
            for doc in await mock_db.contract_leads.find().sort("score", -1).skip(1).limit(2).to_list(5)
        ]
        monty_page = [
            doc["name"] for doc in _monty_collection().find().sort("score", -1).skip(1).limit(2)
        ]
        assert mock_page == monty_page


class TestBuiltQueriesRunOnBothEngines:
    """The query builder output must be valid Mongo, not just valid Python."""

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"search": "Kopi"},
            {"region": "bogor"},
            {"lead_status": None, "search": "jakarta"},
            {"min_score": 0, "max_score": 39},
            {"search": "a.b*c[", "region": None},  # regex metacharacters must be escaped
        ],
    )
    async def test_builder_output_executes_identically(self, kwargs, mock_db):
        from app.models.common import LeadStatus  # noqa: F401 - used via kwargs

        user = {"role": "admin_internal"}  # admin => no tenant filter to strip
        query = build_lead_query(
            user,
            kwargs.get("project_id"),
            kwargs.get("region"),
            kwargs.get("lead_status"),
            kwargs.get("search"),
            kwargs.get("min_score"),
            kwargs.get("max_score"),
        )
        await mock_db.contract_leads.insert_many([dict(doc) for doc in SAMPLE])
        mock_names = sorted(d["name"] for d in await mock_db.contract_leads.find(query).to_list(50))
        monty_names = sorted(d["name"] for d in _monty_collection().find(query))
        assert mock_names == monty_names

    async def test_search_input_cannot_act_as_a_regex(self, mock_db):
        """A user typing regex metacharacters must not match everything."""
        await mock_db.contract_leads.insert_many([dict(doc) for doc in SAMPLE])
        query = build_lead_query({"role": "admin_internal"}, None, None, None, ".*", None, None)
        assert await mock_db.contract_leads.count_documents(query) == 0


class TestIndexConstraints:
    async def test_indexes_exist_after_bootstrap(self, mock_db):
        users = await mock_db.users.index_information()
        assert "email_1" in users
        leads = await mock_db.leads.index_information()
        assert "leads_text_search" in leads
        jobs = await mock_db.scrape_jobs.index_information()
        assert "status_1_created_at_1" in jobs

    async def test_duplicate_email_is_rejected_by_the_database(self, mock_db):
        """The registration race fallback relies on this constraint existing."""
        await mock_db.users.insert_one({"email": "kembar@agency.co.id", "name": "A"})
        with pytest.raises(DuplicateKeyError):
            await mock_db.users.insert_one({"email": "kembar@agency.co.id", "name": "B"})

    async def test_register_endpoint_survives_a_duplicate(self, client, mock_db):
        payload = {
            "company_name": "Agency Kembar",
            "name": "Budi",
            "email": "kembar2@agency.co.id",
            "password": "password-kuat-123",
        }
        assert (await client.post("/api/auth/register", json=payload)).status_code == 201
        second = await client.post("/api/auth/register", json=payload)
        assert second.status_code == 409
        # The rolled-back tenant must not be left behind.
        assert await mock_db.tenants.count_documents({"company_name": "Agency Kembar"}) == 1
