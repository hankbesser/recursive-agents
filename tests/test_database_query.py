import sys
from pathlib import Path
import pytest
import aiosqlite

# Add the recursive-agents-mcp directory to sys.path
sys.path.append(str(Path(__file__).resolve().parents[1] / "recursive-agents-mcp"))
from core.data_tools import DataTools

@pytest.mark.asyncio
async def test_database_query_sqlite(tmp_path):
    db_file = tmp_path / "test.db"
    async with aiosqlite.connect(db_file) as db:
        await db.execute("CREATE TABLE items(id INTEGER PRIMARY KEY, name TEXT)")
        await db.execute("INSERT INTO items(name) VALUES ('apple'),('banana')")
        await db.commit()

    tools = DataTools()
    result = await tools.database_query(
        "SELECT name FROM items ORDER BY id", {"database": str(db_file)}, "sqlite"
    )

    assert result["status"] == "success"
    assert result["rows"] == [{"name": "apple"}, {"name": "banana"}]
