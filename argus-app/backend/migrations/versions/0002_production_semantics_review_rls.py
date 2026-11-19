"""Production semantics, observation/disposition/review tables, and scoped RLS"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    # ── 1. Intake & financial semantics provenance columns ──
    op.add_column("import_batch", sa.Column("schema_version", sa.String(length=32), nullable=False, server_default="canonical-csv-v1"))
    op.add_column("import_batch", sa.Column("transformation_version", sa.String(length=32), nullable=False, server_default="argus-intake-v1"))
    op.add_column("import_batch", sa.Column("extract_id", sa.String(length=128), nullable=True))

    op.add_column("source_file", sa.Column("extract_id", sa.String(length=128), nullable=True))
    op.add_column("source_file", sa.Column("filename", sa.String(length=255), nullable=True))

    op.add_column("ledger_record", sa.Column("event_status", sa.String(length=32), nullable=False, server_default="POSTED"))
    op.add_column("ledger_record", sa.Column("analysis_eligible", sa.Boolean(), nullable=False, server_default=sa.text("true")))
    op.add_column("ledger_record", sa.Column("exclusion_reason", sa.String(length=64), nullable=True))
    op.add_column("ledger_record", sa.Column("posting_group_id", sa.String(length=128), nullable=True))
    op.add_column("ledger_record", sa.Column("transformation_version", sa.String(length=32), nullable=False, server_default="argus-intake-v1"))
    op.create_check_constraint(
        "ck_ledger_record_event_status",
        "ledger_record",
        "event_status IN ('POSTED','PENDING','CANCELLED')",
    )

    # ── 2. Snapshot explicit sealing (avoids 32-bit xid wraparound reliance) ──
    op.add_column("snapshot", sa.Column("sealed", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    # Mark any pre-existing snapshots sealed before enabling seal-aware triggers.
    op.execute("DROP TRIGGER immutable_evidence ON snapshot")
    op.execute("UPDATE snapshot SET sealed = true")
    op.execute("""
        CREATE FUNCTION protect_snapshot_row() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'Published snapshots are immutable' USING ERRCODE = '23514';
            END IF;
            IF OLD.sealed = false AND NEW.sealed = true
               AND (to_jsonb(NEW) - 'sealed') IS NOT DISTINCT FROM (to_jsonb(OLD) - 'sealed') THEN
                RETURN NEW;
            END IF;
            RAISE EXCEPTION 'Published snapshots are immutable' USING ERRCODE = '23514';
        END $$
    """)
    op.execute(
        "CREATE TRIGGER immutable_snapshot BEFORE UPDATE OR DELETE ON snapshot "
        "FOR EACH ROW EXECUTE FUNCTION protect_snapshot_row()"
    )
    op.execute("""
        CREATE OR REPLACE FUNCTION protect_snapshot_membership() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM snapshot WHERE id = NEW.snapshot_id AND sealed = false) THEN
                RAISE EXCEPTION 'Snapshot membership is sealed' USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END $$
    """)

    # ── 3. Case, artifact, approval & export extensions ──
    op.add_column("case_record", sa.Column("closed_reason", sa.String(length=64), nullable=True))
    op.add_column("case_record", sa.Column("closure_memo", sa.String(length=4000), nullable=True))
    op.add_column("case_record", sa.Column("active_job_id", sa.String(length=36), nullable=True))

    op.add_column("artifact", sa.Column("parent_artifact_id", sa.String(length=36), nullable=True))
    op.add_column("artifact", sa.Column("revision_number", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("artifact", sa.Column("policy_version", sa.String(length=64), nullable=False, server_default="policy-v1"))
    op.add_column("artifact", sa.Column("validator_version", sa.String(length=64), nullable=False, server_default="validator-v1"))
    op.add_column("artifact", sa.Column("narrative_sha256", sa.String(length=64), nullable=False, server_default=""))
    op.add_column("artifact", sa.Column("manifest_sha256", sa.String(length=64), nullable=False, server_default=""))
    op.add_column("artifact", sa.Column("contributors_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")))
    op.create_foreign_key("fk_artifact_parent", "artifact", "artifact", ["parent_artifact_id"], ["id"])

    op.add_column("approval", sa.Column("decision", sa.String(length=32), nullable=False, server_default="APPROVED"))
    op.add_column("approval", sa.Column("review_note", sa.String(length=4000), nullable=True))
    op.add_column("approval", sa.Column("envelope_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")))
    op.add_column("approval", sa.Column("envelope_digest", sa.String(length=64), nullable=False, server_default=""))
    op.create_check_constraint(
        "ck_approval_decision",
        "approval",
        "decision IN ('APPROVED','CHANGES_REQUESTED')",
    )

    op.add_column("export", sa.Column("export_kind", sa.String(length=32), nullable=False, server_default="CURRENT"))
    op.add_column("export", sa.Column("dataset_generation_at_export", sa.Integer(), nullable=False, server_default="0"))
    op.create_check_constraint(
        "ck_export_kind",
        "export",
        "export_kind IN ('CURRENT','HISTORICAL')",
    )

    # ── 4. Durable observations, dispositions & non-authorship comments ──
    op.create_table(
        "case_observation",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("case_id", sa.String(length=36), nullable=False),
        sa.Column("dataset_id", sa.String(length=36), nullable=False),
        sa.Column("snapshot_id", sa.String(length=36), nullable=False),
        sa.Column("source_kind", sa.String(length=32), nullable=False),
        sa.Column("source_ref", sa.String(length=255), nullable=False),
        sa.Column("span_start", sa.Integer(), nullable=True),
        sa.Column("span_end", sa.Integer(), nullable=True),
        sa.Column("entity_id", sa.String(length=128), nullable=True),
        sa.Column("account_id", sa.String(length=128), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=True),
        sa.Column("interval_start", sa.String(length=64), nullable=True),
        sa.Column("interval_end", sa.String(length=64), nullable=True),
        sa.Column("accounting_basis", sa.String(length=32), nullable=True),
        sa.Column("aggregation", sa.String(length=32), nullable=True),
        sa.Column("amount_str", sa.String(length=64), nullable=True),
        sa.Column("raw_text", sa.String(length=8000), nullable=False),
        sa.Column("scope_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("comparison_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_by", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(["case_id", "dataset_id"], ["case_record.id", "case_record.dataset_id"]),
        sa.ForeignKeyConstraint(["snapshot_id", "dataset_id"], ["snapshot.id", "snapshot.dataset_id"]),
        sa.ForeignKeyConstraint(["created_by"], ["app_user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "case_finding_disposition",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("case_id", sa.String(length=36), nullable=False),
        sa.Column("dataset_id", sa.String(length=36), nullable=False),
        sa.Column("job_id", sa.String(length=36), nullable=True),
        sa.Column("finding_id", sa.String(length=128), nullable=False),
        sa.Column("disposition", sa.String(length=32), nullable=False),
        sa.Column("rationale", sa.String(length=4000), nullable=False),
        sa.Column("benign_alternative", sa.String(length=4000), nullable=True),
        sa.Column("actor_id", sa.String(length=36), nullable=False),
        sa.CheckConstraint("disposition IN ('OPEN','ESCALATED','DISMISSED','NEEDS_INFO')"),
        sa.ForeignKeyConstraint(["case_id", "dataset_id"], ["case_record.id", "case_record.dataset_id"]),
        sa.ForeignKeyConstraint(["job_id"], ["job.id"]),
        sa.ForeignKeyConstraint(["actor_id"], ["app_user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "case_comment",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("case_id", sa.String(length=36), nullable=False),
        sa.Column("dataset_id", sa.String(length=36), nullable=False),
        sa.Column("artifact_id", sa.String(length=36), nullable=True),
        sa.Column("author_id", sa.String(length=36), nullable=False),
        sa.Column("body", sa.String(length=4000), nullable=False),
        sa.ForeignKeyConstraint(["case_id", "dataset_id"], ["case_record.id", "case_record.dataset_id"]),
        sa.ForeignKeyConstraint(["artifact_id"], ["artifact.id"]),
        sa.ForeignKeyConstraint(["author_id"], ["app_user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    for table in ("case_observation", "case_finding_disposition", "case_comment"):
        op.execute(
            f"CREATE TRIGGER immutable_evidence BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION reject_evidence_mutation()"
        )

    # ── 5. Narrowly scoped PostgreSQL RLS policies for case isolation ──
    # Applies to non-owner, non-BYPASSRLS roles (e.g. argus_app) when transaction-local
    # app.current_user_id is set. Worker / auditor / administrator flows explicitly set
    # SET LOCAL app.rls_bypass = 'true' after passing central authorization.
    op.execute("ALTER TABLE case_record ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY case_record_select_policy ON case_record FOR SELECT
        USING (
            current_setting('app.rls_bypass', true) = 'true'
            OR EXISTS (
                SELECT 1 FROM case_assignment ca
                WHERE ca.case_id = case_record.id
                  AND ca.user_id = current_setting('app.current_user_id', true)
            )
        )
    """)
    op.execute("""
        CREATE POLICY case_record_insert_policy ON case_record FOR INSERT
        WITH CHECK (
            current_setting('app.rls_bypass', true) = 'true'
            OR created_by = current_setting('app.current_user_id', true)
        )
    """)
    op.execute("""
        CREATE POLICY case_record_update_policy ON case_record FOR UPDATE
        USING (
            current_setting('app.rls_bypass', true) = 'true'
            OR EXISTS (
                SELECT 1 FROM case_assignment ca
                WHERE ca.case_id = case_record.id
                  AND ca.user_id = current_setting('app.current_user_id', true)
            )
        )
        WITH CHECK (
            current_setting('app.rls_bypass', true) = 'true'
            OR EXISTS (
                SELECT 1 FROM case_assignment ca
                WHERE ca.case_id = case_record.id
                  AND ca.user_id = current_setting('app.current_user_id', true)
            )
        )
    """)

    for child_table in ("case_observation", "case_finding_disposition", "case_comment", "artifact"):
        op.execute(f"ALTER TABLE {child_table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"""
            CREATE POLICY {child_table}_case_scope_policy ON {child_table}
            USING (
                current_setting('app.rls_bypass', true) = 'true'
                OR EXISTS (
                    SELECT 1 FROM case_assignment ca
                    WHERE ca.case_id = {child_table}.case_id
                      AND ca.user_id = current_setting('app.current_user_id', true)
                )
            )
            WITH CHECK (
                current_setting('app.rls_bypass', true) = 'true'
                OR EXISTS (
                    SELECT 1 FROM case_assignment ca
                    WHERE ca.case_id = {child_table}.case_id
                      AND ca.user_id = current_setting('app.current_user_id', true)
                )
            )
        """)

    op.execute("ALTER TABLE export ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY export_case_scope_policy ON export
        USING (
            current_setting('app.rls_bypass', true) = 'true'
            OR EXISTS (
                SELECT 1 FROM artifact a
                JOIN case_assignment ca ON ca.case_id = a.case_id
                WHERE a.id = export.artifact_id
                  AND ca.user_id = current_setting('app.current_user_id', true)
            )
        )
        WITH CHECK (
            current_setting('app.rls_bypass', true) = 'true'
            OR EXISTS (
                SELECT 1 FROM artifact a
                JOIN case_assignment ca ON ca.case_id = a.case_id
                WHERE a.id = export.artifact_id
                  AND ca.user_id = current_setting('app.current_user_id', true)
            )
        )
    """)


def downgrade():
    raise RuntimeError("Destructive rollback requires an approved restore procedure")
