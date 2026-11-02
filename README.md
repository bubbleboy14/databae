# databae

DATabase ABstraction lAyEr

v0.2.1.7

Database recovery settings live in `databae.config.config`:

```python
from databae.config import config

config.timeout.update("read", 30)
config.timeout.update("write", 30)
config.timeout.update("connect", 10)
config.retry.update("reads", 2)
config.retry.update("delay", 0.25)
```

The timeout values are seconds and apply to MySQL/MariaDB connections using
PyMySQL. Explicit timeout settings in the database URL take precedence. Other
drivers keep their own connection settings; SQLite receives no PyMySQL options.

`retry.reads` is the number of additional attempts after a transient connection
failure on `get()`, `all()`, or `count()`. Two retries means three attempts, with
delays of 0.25 and 0.5 seconds by default. These are per-attempt socket timeouts,
not a deadline for the whole operation. Set `config.retry.update("reads", 0)`
to disable retries.

Transparent retries require an independent SELECT with an engine-bound, reusable
ORM session, no existing transaction, and no pending or loaded objects. Sessions
created with `close_resets_only=False` cannot retry after invalidation. Locking reads
and reads that flush writes are excluded. A failed connection is invalidated
before another attempt so it cannot be reused.

Other failures roll back the session and raise the original exception. Writes
and transactions are never automatically replayed after connection failure: the
caller must decide whether to retry the entire operation, including handling an
ambiguous commit result. The existing optional missing-column repair still gets
one retry after repair.
