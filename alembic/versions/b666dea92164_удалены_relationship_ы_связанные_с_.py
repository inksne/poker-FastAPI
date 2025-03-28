"""удалены relationship'ы, связанные с TablePlayer

Revision ID: b666dea92164
Revises: 6d192057ad8e
Create Date: 2025-03-08 18:54:04.279460

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b666dea92164'
down_revision: Union[str, None] = '6d192057ad8e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('table_players')
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('table_players',
    sa.Column('table_id', sa.INTEGER(), autoincrement=False, nullable=False),
    sa.Column('user_id', sa.INTEGER(), autoincrement=False, nullable=False),
    sa.ForeignKeyConstraint(['table_id'], ['tables.id'], name='table_players_table_id_fkey'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='table_players_user_id_fkey'),
    sa.PrimaryKeyConstraint('table_id', 'user_id', name='table_players_pkey')
    )
    # ### end Alembic commands ###
