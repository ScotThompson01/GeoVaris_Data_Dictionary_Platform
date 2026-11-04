"""Create Phase 5E execution protection persistence.

Revision ID: 0025
Revises: 0024

PostgreSQL-specific, statically generated migration draft.

REVIEW REQUIRED BEFORE APPLYING:
- Existing schema and Alembic revision must be independently checked.
- Constraint names and source identity relationships require PostgreSQL tests.
- No application runtime execution admission is authorized by this migration.
"""

from alembic import op
import sqlalchemy as sa


revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint('uq_data_source_project_identity', 'data_sources', ['id', 'project_id'])
    op.create_unique_constraint('uq_source_object_source_identity', 'source_objects', ['id', 'data_source_id'])
    op.create_unique_constraint('uq_data_field_object_identity', 'data_fields', ['id', 'source_object_id'])
    op.create_unique_constraint('uq_dq_rule_field_identity', 'data_quality_rules', ['id', 'data_field_id'])
    op.create_unique_constraint('uq_dq_execution_project_rule_identity', 'data_quality_rule_executions', ['id', 'project_id', 'rule_id'])

    op.execute(sa.text('CREATE TABLE data_quality_workload_resolution_grants (\n\tid UUID NOT NULL, \n\tproject_id UUID NOT NULL, \n\tuser_id UUID NOT NULL, \n\tgranted_by_user_id UUID NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\trevoked_at TIMESTAMP WITH TIME ZONE, \n\tPRIMARY KEY (id), \n\tCONSTRAINT uq_dq_resolution_grant_id_project_user UNIQUE (id, project_id, user_id), \n\tCONSTRAINT uq_dq_resolution_grant_project_user UNIQUE (project_id, user_id), \n\tFOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE RESTRICT, \n\tFOREIGN KEY(user_id) REFERENCES users (id) ON DELETE RESTRICT, \n\tFOREIGN KEY(granted_by_user_id) REFERENCES users (id) ON DELETE RESTRICT\n)'))
    op.execute(sa.text('CREATE INDEX ix_dq_resolution_grant_project ON data_quality_workload_resolution_grants (project_id)'))

    op.execute(sa.text("CREATE TABLE data_quality_execution_capacity_controls (\n\tid UUID NOT NULL, \n\tscope_type VARCHAR(30) NOT NULL, \n\tdata_source_id UUID, \n\tmax_concurrent INTEGER NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tPRIMARY KEY (id), \n\tCONSTRAINT uq_dq_capacity_control_id_scope_source UNIQUE (id, scope_type, data_source_id), \n\tCONSTRAINT uq_dq_capacity_control_id_scope UNIQUE (id, scope_type), \n\tCONSTRAINT ck_dq_capacity_control_scope CHECK (scope_type IN ('installation', 'source')), \n\tCONSTRAINT ck_dq_capacity_control_positive_limit CHECK (max_concurrent >= 1), \n\tCONSTRAINT ck_dq_capacity_control_source_scope CHECK ((scope_type = 'installation' AND data_source_id IS NULL) OR (scope_type = 'source' AND data_source_id IS NOT NULL)), \n\tCONSTRAINT uq_dq_capacity_control_data_source UNIQUE (data_source_id), \n\tFOREIGN KEY(data_source_id) REFERENCES data_sources (id) ON DELETE RESTRICT\n)"))
    op.execute(sa.text("CREATE UNIQUE INDEX uq_dq_capacity_single_installation ON data_quality_execution_capacity_controls (scope_type) WHERE scope_type = 'installation'"))

    op.execute(sa.text("CREATE TABLE data_quality_workload_ownership (\n\tid UUID NOT NULL, \n\texecution_id UUID NOT NULL, \n\tproject_id UUID NOT NULL, \n\trule_id UUID NOT NULL, \n\tdata_field_id UUID NOT NULL, \n\tsource_object_id UUID NOT NULL, \n\tdata_source_id UUID NOT NULL, \n\tscope_type VARCHAR(50) DEFAULT 'full_object' NOT NULL, \n\townership_state VARCHAR(50) DEFAULT 'reserved' NOT NULL, \n\treleased_at TIMESTAMP WITH TIME ZONE, \n\trelease_actor VARCHAR(255), \n\trelease_reason VARCHAR(1000), \n\trelease_evidence_reference VARCHAR(1000), \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tPRIMARY KEY (id), \n\tCONSTRAINT uq_dq_workload_id_project_source UNIQUE (id, project_id, data_source_id), \n\tCONSTRAINT uq_dq_workload_id_source UNIQUE (id, data_source_id), \n\tCONSTRAINT fk_dq_workload_rule_field_identity FOREIGN KEY(rule_id, data_field_id) REFERENCES data_quality_rules (id, data_field_id) ON DELETE RESTRICT, \n\tCONSTRAINT fk_dq_workload_field_object_identity FOREIGN KEY(data_field_id, source_object_id) REFERENCES data_fields (id, source_object_id) ON DELETE RESTRICT, \n\tCONSTRAINT fk_dq_workload_source_object_identity FOREIGN KEY(source_object_id, data_source_id) REFERENCES source_objects (id, data_source_id) ON DELETE RESTRICT, \n\tCONSTRAINT fk_dq_workload_data_source_identity FOREIGN KEY(data_source_id, project_id) REFERENCES data_sources (id, project_id) ON DELETE RESTRICT, \n\tCONSTRAINT fk_dq_workload_execution_identity FOREIGN KEY(execution_id, project_id, rule_id) REFERENCES data_quality_rule_executions (id, project_id, rule_id) ON DELETE RESTRICT, \n\tCONSTRAINT ck_dq_workload_release_audit CHECK ((ownership_state = 'released' AND released_at IS NOT NULL AND NULLIF(BTRIM(release_actor), '') IS NOT NULL AND NULLIF(BTRIM(release_reason), '') IS NOT NULL AND NULLIF(BTRIM(release_evidence_reference), '') IS NOT NULL) OR (ownership_state IN ('reserved', 'unresolved') AND released_at IS NULL AND release_actor IS NULL AND release_reason IS NULL AND release_evidence_reference IS NULL)), \n\tCONSTRAINT ck_dq_workload_scope CHECK (scope_type = 'full_object'), \n\tCONSTRAINT ck_dq_workload_state CHECK (ownership_state IN ('reserved', 'unresolved', 'released')), \n\tUNIQUE (execution_id), \n\tFOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE RESTRICT, \n\tFOREIGN KEY(rule_id) REFERENCES data_quality_rules (id) ON DELETE RESTRICT, \n\tFOREIGN KEY(source_object_id) REFERENCES source_objects (id) ON DELETE RESTRICT, \n\tFOREIGN KEY(data_source_id) REFERENCES data_sources (id) ON DELETE RESTRICT\n)"))
    op.execute(sa.text('CREATE INDEX ix_dq_workload_data_source_state ON data_quality_workload_ownership (data_source_id, ownership_state)'))
    op.execute(sa.text("CREATE UNIQUE INDEX uq_dq_active_workload_identity ON data_quality_workload_ownership (rule_id, source_object_id, scope_type) WHERE ownership_state IN ('reserved', 'unresolved')"))

    op.execute(sa.text("CREATE TABLE data_quality_execution_capacity_reservations (\n\tid UUID NOT NULL, \n\townership_id UUID NOT NULL, \n\tcapacity_control_id UUID NOT NULL, \n\townership_data_source_id UUID NOT NULL, \n\tdata_source_id UUID, \n\treservation_scope VARCHAR(30) NOT NULL, \n\treservation_state VARCHAR(30) DEFAULT 'reserved' NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\trelease_actor VARCHAR(255), \n\trelease_reason VARCHAR(1000), \n\trelease_evidence_reference VARCHAR(1000), \n\treleased_at TIMESTAMP WITH TIME ZONE, \n\tPRIMARY KEY (id), \n\tCONSTRAINT fk_dq_reservation_ownership_source FOREIGN KEY(ownership_id, ownership_data_source_id) REFERENCES data_quality_workload_ownership (id, data_source_id) ON DELETE RESTRICT, \n\tCONSTRAINT fk_dq_reservation_capacity_source FOREIGN KEY(capacity_control_id, reservation_scope, data_source_id) REFERENCES data_quality_execution_capacity_controls (id, scope_type, data_source_id) ON DELETE RESTRICT, \n\tCONSTRAINT ck_dq_reservation_source_scope CHECK ((reservation_scope = 'installation' AND data_source_id IS NULL) OR (reservation_scope = 'source' AND data_source_id IS NOT NULL AND data_source_id = ownership_data_source_id)), \n\tCONSTRAINT fk_dq_reservation_capacity_scope FOREIGN KEY(capacity_control_id, reservation_scope) REFERENCES data_quality_execution_capacity_controls (id, scope_type) ON DELETE RESTRICT, \n\tCONSTRAINT ck_dq_reservation_scope CHECK (reservation_scope IN ('installation', 'source')), \n\tCONSTRAINT ck_dq_reservation_state CHECK (reservation_state IN ('reserved', 'unresolved', 'released')), \n\tCONSTRAINT ck_dq_reservation_release_audit CHECK ((reservation_state = 'released' AND released_at IS NOT NULL AND NULLIF(BTRIM(release_actor), '') IS NOT NULL AND NULLIF(BTRIM(release_reason), '') IS NOT NULL AND NULLIF(BTRIM(release_evidence_reference), '') IS NOT NULL) OR (reservation_state IN ('reserved', 'unresolved') AND released_at IS NULL AND release_actor IS NULL AND release_reason IS NULL AND release_evidence_reference IS NULL)), \n\tCONSTRAINT uq_dq_reservation_ownership_scope UNIQUE (ownership_id, reservation_scope), \n\tCONSTRAINT fk_dq_reservation_ownership FOREIGN KEY(ownership_id) REFERENCES data_quality_workload_ownership (id) ON DELETE RESTRICT\n)"))
    op.execute(sa.text('CREATE INDEX ix_dq_reservation_capacity_state ON data_quality_execution_capacity_reservations (capacity_control_id, reservation_state)'))

    op.execute(sa.text("CREATE TABLE data_quality_workload_release_evidence (\n\tid UUID NOT NULL, \n\townership_id UUID NOT NULL, \n\tproject_id UUID NOT NULL, \n\tdata_source_id UUID NOT NULL, \n\tactor_user_id UUID NOT NULL, \n\tresolution_grant_id UUID, \n\tevidence_type VARCHAR(50) NOT NULL, \n\tevidence_status VARCHAR(30) DEFAULT 'recorded' NOT NULL, \n\treason VARCHAR(1000) NOT NULL, \n\tevidence_reference VARCHAR(1000) NOT NULL, \n\tverified_by_user_id UUID, \n\tverified_at TIMESTAMP WITH TIME ZONE, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tPRIMARY KEY (id), \n\tCONSTRAINT fk_dq_release_evidence_workload_identity FOREIGN KEY(ownership_id, project_id, data_source_id) REFERENCES data_quality_workload_ownership (id, project_id, data_source_id) ON DELETE RESTRICT, \n\tCONSTRAINT fk_dq_release_evidence_resolution_grant_identity FOREIGN KEY(resolution_grant_id, project_id, actor_user_id) REFERENCES data_quality_workload_resolution_grants (id, project_id, user_id) ON DELETE RESTRICT, \n\tCONSTRAINT ck_dq_release_evidence_type CHECK (evidence_type IN ('verified_source_termination', 'authorized_admin_resolution')), \n\tCONSTRAINT ck_dq_release_evidence_status CHECK (evidence_status IN ('recorded', 'confirmed', 'rejected')), \n\tCONSTRAINT ck_dq_release_evidence_grant_type CHECK ((evidence_type = 'verified_source_termination' AND resolution_grant_id IS NULL) OR (evidence_type = 'authorized_admin_resolution' AND resolution_grant_id IS NOT NULL)), \n\tCONSTRAINT ck_dq_release_evidence_review_state CHECK ((evidence_status = 'recorded' AND verified_at IS NULL AND verified_by_user_id IS NULL) OR (evidence_status IN ('confirmed', 'rejected') AND verified_at IS NOT NULL AND verified_by_user_id IS NOT NULL)), \n\tCONSTRAINT ck_dq_release_evidence_required_details CHECK (NULLIF(BTRIM(reason), '') IS NOT NULL AND NULLIF(BTRIM(evidence_reference), '') IS NOT NULL), \n\tFOREIGN KEY(actor_user_id) REFERENCES users (id) ON DELETE RESTRICT, \n\tFOREIGN KEY(verified_by_user_id) REFERENCES users (id) ON DELETE RESTRICT\n)"))
    op.execute(sa.text('CREATE INDEX ix_dq_release_evidence_ownership_status ON data_quality_workload_release_evidence (ownership_id, evidence_status)'))


def downgrade() -> None:
    op.drop_table('data_quality_workload_release_evidence')
    op.drop_table('data_quality_execution_capacity_reservations')
    op.drop_table('data_quality_workload_ownership')
    op.drop_table('data_quality_execution_capacity_controls')
    op.drop_table('data_quality_workload_resolution_grants')

    op.drop_constraint('uq_dq_execution_project_rule_identity', 'data_quality_rule_executions', type_='unique')
    op.drop_constraint('uq_dq_rule_field_identity', 'data_quality_rules', type_='unique')
    op.drop_constraint('uq_data_field_object_identity', 'data_fields', type_='unique')
    op.drop_constraint('uq_source_object_source_identity', 'source_objects', type_='unique')
    op.drop_constraint('uq_data_source_project_identity', 'data_sources', type_='unique')
