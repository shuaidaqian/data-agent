from sql_agent.context.conversation import ConversationManager


class TestConversationManager:
    def test_create(self):
        mgr = ConversationManager()
        conv = mgr.create_conversation("db1")
        assert conv.db_connection_id == "db1"

    def test_get_or_create_new(self):
        mgr = ConversationManager()
        conv = mgr.get_or_create(db_connection_id="db1")
        assert conv.db_connection_id == "db1"

    def test_get_or_create_existing(self):
        mgr = ConversationManager()
        c1 = mgr.create_conversation("db1")
        c2 = mgr.get_or_create(conversation_id=c1.id)
        assert c1.id == c2.id

    def test_add_turn(self):
        mgr = ConversationManager()
        conv = mgr.create_conversation("db1")
        mgr.add_turn(conv, "user", "Q1")
        assert len(conv.turns) == 1

    def test_add_turn_with_sql(self):
        mgr = ConversationManager()
        conv = mgr.create_conversation("db1")
        mgr.add_turn(conv, "assistant", "A1", sql="SELECT * FROM t")
        assert conv.turns[0].sql == "SELECT * FROM t"

    def test_build_context(self):
        mgr = ConversationManager()
        conv = mgr.create_conversation("db1")
        mgr.add_turn(conv, "user", "Show departments")
        mgr.add_turn(
            conv, "assistant", "SELECT * FROM departments", sql="SELECT * FROM departments"
        )
        ctx = mgr.build_context_prompt(conv, "Show employees")
        assert "departments" in ctx
        assert "SELECT" in ctx

    def test_truncation(self):
        mgr = ConversationManager(max_turns=4)
        conv = mgr.create_conversation("db1")
        for i in range(6):
            mgr.add_turn(conv, "user", f"Q{i}")
        assert len(conv.turns) == 4

    def test_get_history(self):
        mgr = ConversationManager()
        conv = mgr.create_conversation("db1")
        for i in range(6):
            mgr.add_turn(conv, "user", f"Q{i}")
        h = mgr.get_relevant_history(conv, "Q4", max_turns=2)
        assert len(h) <= 4

    def test_delete(self):
        mgr = ConversationManager()
        conv = mgr.create_conversation("db1")
        assert mgr.delete_conversation(str(conv.id) if conv.id else "fake")

    def test_summary(self):
        mgr = ConversationManager()
        conv = mgr.create_conversation("db1")
        mgr.add_turn(conv, "user", "Show employees")
        s = mgr.get_conversation_summary(conv)
        assert "employees" in s or "1" in s
