from alembic import context

with context.config.attributes["connection"].begin_nested():
    context.configure(connection=context.config.attributes["connection"],transactional_ddl=True)
    with context.begin_transaction():
        context.run_migrations()
