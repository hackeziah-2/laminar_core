"""Migration checks for technical logbook logbook_seq_no column."""
from unittest.mock import MagicMock, patch

from alembic.config import Config
from alembic.script import ScriptDirectory


def test_logbook_seq_no_migration_is_head_child_and_reversible():
    """Ensure migration revises current head and exposes upgrade/downgrade."""
    config = Config("alembic.ini")
    script = ScriptDirectory.from_config(config)
    rev = script.get_revision("bb1cc2dd3ee4")

    assert rev is not None
    assert rev.down_revision == "aa0bb1cc2dd3"
    assert "bb1cc2dd3ee4" in script.get_heads()

    module = rev.module
    assert callable(getattr(module, "upgrade", None))
    assert callable(getattr(module, "downgrade", None))
    assert module._LOGBOOK_TABLES == (
        "airframe_logbook",
        "engine_logbook",
        "avionics_logbook",
        "propeller_logbook",
    )


def test_logbook_seq_no_migration_upgrade_and_downgrade_ops():
    """Exercise upgrade/downgrade against mocked Alembic op (safe backfill path)."""
    config = Config("alembic.ini")
    script = ScriptDirectory.from_config(config)
    module = script.get_revision("bb1cc2dd3ee4").module

    mock_op = MagicMock()
    with patch.object(module, "op", mock_op):
        module.upgrade()
        module.downgrade()

    assert mock_op.add_column.call_count == 4
    assert mock_op.alter_column.call_count == 4
    assert mock_op.create_index.call_count == 4
    assert mock_op.drop_index.call_count == 4
    assert mock_op.drop_column.call_count == 4
    # Two UPDATE statements per table (copy sequence_no, then fallback).
    assert mock_op.execute.call_count == 8

    for table_name in module._LOGBOOK_TABLES:
        mock_op.create_index.assert_any_call(
            f"ix_{table_name}_logbook_seq_no",
            table_name,
            ["logbook_seq_no"],
            unique=False,
        )
        mock_op.drop_index.assert_any_call(
            f"ix_{table_name}_logbook_seq_no",
            table_name=table_name,
        )
        mock_op.drop_column.assert_any_call(table_name, "logbook_seq_no")

    # First add_column is nullable=True (safe backfill before NOT NULL).
    first_add = mock_op.add_column.call_args_list[0]
    column = first_add.args[1]
    assert first_add.args[0] == "airframe_logbook"
    assert column.name == "logbook_seq_no"
    assert column.nullable is True
