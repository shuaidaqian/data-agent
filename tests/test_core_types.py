from sql_agent.core.types import Prompt, SQLGeneration, Conversation, ConversationTurn, SQLStatus


class TestPrompt:
    def test_create(self):
        p = Prompt(text="Show all employees", db_connection_id="db1")
        assert p.text == "Show all employees"
        assert p.db_connection_id == "db1"


class TestSQLGeneration:
    def test_default_status(self):
        gen = SQLGeneration(prompt_id="p1")
        assert gen.status == "PENDING"
        assert gen.correction_rounds == 0

    def test_with_sql(self):
        gen = SQLGeneration(prompt_id="p1", sql="SELECT * FROM t", status=SQLStatus.VALID)
        assert gen.status == "VALID"
        assert gen.sql_before_correction is None

    def test_correction_fields(self):
        gen = SQLGeneration(
            prompt_id="p1",
            sql="SELECT * FROM t",
            sql_before_correction="SELECT * FROM wrong",
            correction_rounds=2,
        )
        assert gen.correction_rounds == 2
        assert gen.sql_before_correction == "SELECT * FROM wrong"


class TestConversation:
    def test_add_turns(self):
        conv = Conversation(db_connection_id="db1")
        turn = ConversationTurn(role="user", content="Show employees")
        conv.turns.append(turn)
        assert len(conv.turns) == 1
        assert conv.turns[0].role == "user"

    def test_timestamps(self):
        conv = Conversation(db_connection_id="db1")
        assert conv.created_at is not None
        assert conv.updated_at is not None
