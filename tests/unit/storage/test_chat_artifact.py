"""Unit tests for chat artifact persistence in DuckDB."""

import json
import pytest
import duckdb


class TestChatArtifactPersistence:
    """Test suite for chat artifact storage and retrieval."""

    @pytest.fixture
    def duckdb_conn(self):
        """Create a minimal DuckDB connection with only chat_artifacts table."""
        conn = duckdb.connect(":memory:")

        # Create only the chat_artifacts table for isolated testing
        conn.execute(
            """
            CREATE TABLE chat_artifacts (
                session_id TEXT NOT NULL,
                message_id TEXT NOT NULL,
                artifact_type TEXT NOT NULL,
                artifact_data JSON NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (session_id, message_id, artifact_type)
            )
        """
        )
        conn.execute(
            "CREATE INDEX idx_chat_artifacts_created_at ON chat_artifacts(created_at)"
        )

        yield conn
        conn.close()

    @pytest.mark.asyncio
    async def test_store_and_retrieve_graph_artifact(self, duckdb_conn):
        """Test storing and retrieving a graph artifact."""
        session_id = "test-session-123"
        message_id = "msg-456"
        graph_data = {
            "nodes": [
                {"id": "n1", "label": "Table", "name": "users"},
                {"id": "n2", "label": "Column", "name": "id"},
            ],
            "edges": [
                {"source": "n1", "target": "n2", "type": "HAS_COLUMN"},
            ],
            "metadata": {"query": "Show users table lineage"},
        }

        # Store the artifact
        json_data = json.dumps(graph_data)
        duckdb_conn.execute(
            """
            INSERT INTO chat_artifacts
                (session_id, message_id, artifact_type, artifact_data)
            VALUES (?, ?, ?, ?)
            ON CONFLICT (session_id, message_id, artifact_type)
            DO UPDATE SET artifact_data = EXCLUDED.artifact_data
            """,
            (session_id, message_id, "graph", json_data),
        )

        # Retrieve the artifact
        result = duckdb_conn.execute(
            """
            SELECT artifact_data
            FROM chat_artifacts
            WHERE session_id = ? AND message_id = ? AND artifact_type = ?
            """,
            (session_id, message_id, "graph"),
        ).fetchone()

        retrieved = json.loads(result[0]) if result else None

        assert retrieved is not None
        assert retrieved["nodes"] == graph_data["nodes"]
        assert retrieved["edges"] == graph_data["edges"]
        assert retrieved["metadata"] == graph_data["metadata"]

    @pytest.mark.asyncio
    async def test_get_nonexistent_artifact_returns_none(self, duckdb_conn):
        """Test that retrieving a non-existent artifact returns None."""
        result = duckdb_conn.execute(
            """
            SELECT artifact_data
            FROM chat_artifacts
            WHERE session_id = ? AND message_id = ? AND artifact_type = ?
            """,
            ("nonexistent-session", "nonexistent-message", "graph"),
        ).fetchone()

        assert result is None

    @pytest.mark.asyncio
    async def test_store_artifact_is_idempotent(self, duckdb_conn):
        """Test that storing the same artifact twice updates it."""
        session_id = "test-session"
        message_id = "msg-1"

        # Store initial artifact
        duckdb_conn.execute(
            """
            INSERT INTO chat_artifacts
                (session_id, message_id, artifact_type, artifact_data)
            VALUES (?, ?, ?, ?)
            ON CONFLICT (session_id, message_id, artifact_type)
            DO UPDATE SET artifact_data = EXCLUDED.artifact_data
            """,
            (session_id, message_id, "graph", json.dumps({"nodes": [{"id": "n1"}], "edges": []})),
        )

        # Store updated artifact with same key
        duckdb_conn.execute(
            """
            INSERT INTO chat_artifacts
                (session_id, message_id, artifact_type, artifact_data)
            VALUES (?, ?, ?, ?)
            ON CONFLICT (session_id, message_id, artifact_type)
            DO UPDATE SET artifact_data = EXCLUDED.artifact_data
            """,
            (session_id, message_id, "graph", json.dumps({"nodes": [{"id": "n1"}, {"id": "n2"}], "edges": []})),
        )

        # Verify only the updated version exists
        result = duckdb_conn.execute(
            """
            SELECT artifact_data
            FROM chat_artifacts
            WHERE session_id = ? AND message_id = ? AND artifact_type = ?
            """,
            (session_id, message_id, "graph"),
        ).fetchone()

        retrieved = json.loads(result[0])
        assert len(retrieved["nodes"]) == 2

    @pytest.mark.asyncio
    async def test_different_artifact_types_are_independent(self, duckdb_conn):
        """Test that different artifact types for the same message are independent."""
        session_id = "test-session"
        message_id = "msg-1"

        # Store graph artifact
        duckdb_conn.execute(
            """
            INSERT INTO chat_artifacts
                (session_id, message_id, artifact_type, artifact_data)
            VALUES (?, ?, ?, ?)
            """,
            (session_id, message_id, "graph", json.dumps({"type": "graph_data"})),
        )

        # Store metadata artifact
        duckdb_conn.execute(
            """
            INSERT INTO chat_artifacts
                (session_id, message_id, artifact_type, artifact_data)
            VALUES (?, ?, ?, ?)
            """,
            (session_id, message_id, "metadata", json.dumps({"type": "metadata_data"})),
        )

        # Retrieve each independently
        graph_result = duckdb_conn.execute(
            "SELECT artifact_data FROM chat_artifacts WHERE session_id = ? AND message_id = ? AND artifact_type = ?",
            (session_id, message_id, "graph"),
        ).fetchone()
        metadata_result = duckdb_conn.execute(
            "SELECT artifact_data FROM chat_artifacts WHERE session_id = ? AND message_id = ? AND artifact_type = ?",
            (session_id, message_id, "metadata"),
        ).fetchone()

        graph = json.loads(graph_result[0])
        metadata = json.loads(metadata_result[0])

        assert graph["type"] == "graph_data"
        assert metadata["type"] == "metadata_data"

    @pytest.mark.asyncio
    async def test_multiple_sessions_are_independent(self, duckdb_conn):
        """Test that artifacts from different sessions are independent."""
        message_id = "msg-1"

        # Store artifact for session 1
        duckdb_conn.execute(
            """
            INSERT INTO chat_artifacts
                (session_id, message_id, artifact_type, artifact_data)
            VALUES (?, ?, ?, ?)
            """,
            ("session-1", message_id, "graph", json.dumps({"session": "one"})),
        )

        # Store artifact for session 2
        duckdb_conn.execute(
            """
            INSERT INTO chat_artifacts
                (session_id, message_id, artifact_type, artifact_data)
            VALUES (?, ?, ?, ?)
            """,
            ("session-2", message_id, "graph", json.dumps({"session": "two"})),
        )

        # Retrieve each independently
        session1_result = duckdb_conn.execute(
            "SELECT artifact_data FROM chat_artifacts WHERE session_id = ? AND message_id = ? AND artifact_type = ?",
            ("session-1", message_id, "graph"),
        ).fetchone()
        session2_result = duckdb_conn.execute(
            "SELECT artifact_data FROM chat_artifacts WHERE session_id = ? AND message_id = ? AND artifact_type = ?",
            ("session-2", message_id, "graph"),
        ).fetchone()

        session1_artifact = json.loads(session1_result[0])
        session2_artifact = json.loads(session2_result[0])

        assert session1_artifact["session"] == "one"
        assert session2_artifact["session"] == "two"

    def test_table_has_correct_schema(self, duckdb_conn):
        """Test that the chat_artifacts table has correct columns."""
        result = duckdb_conn.execute(
            """
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'chat_artifacts'
            ORDER BY ordinal_position
            """
        ).fetchall()

        columns = {row[0]: row[1] for row in result}

        assert "session_id" in columns
        assert "message_id" in columns
        assert "artifact_type" in columns
        assert "artifact_data" in columns
        assert "created_at" in columns

    def test_index_exists_on_created_at(self, duckdb_conn):
        """Test that the created_at index exists."""
        result = duckdb_conn.execute(
            """
            SELECT COUNT(*) FROM duckdb_indexes()
            WHERE index_name = 'idx_chat_artifacts_created_at'
            """
        ).fetchone()

        assert result[0] == 1

    def test_primary_key_prevents_duplicates(self, duckdb_conn):
        """Test that primary key prevents duplicate entries."""
        # Insert first artifact
        duckdb_conn.execute(
            """
            INSERT INTO chat_artifacts
                (session_id, message_id, artifact_type, artifact_data)
            VALUES (?, ?, ?, ?)
            """,
            ("session", "msg", "graph", json.dumps({"v": 1})),
        )

        # Try to insert duplicate - should fail
        with pytest.raises(duckdb.ConstraintException):
            duckdb_conn.execute(
                """
                INSERT INTO chat_artifacts
                    (session_id, message_id, artifact_type, artifact_data)
                VALUES (?, ?, ?, ?)
                """,
                ("session", "msg", "graph", json.dumps({"v": 2})),
            )
