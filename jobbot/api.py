import asyncio
import hmac
import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse

from jobbot.core import LOCK, config, db, event, excel, now, root, rows, run


def auth(authorization: str = Header(default='')):
    token = os.getenv('API_TOKEN', '')
    if not token or not hmac.compare_digest(authorization, 'Bearer ' + token):
        raise HTTPException(status_code=401, detail='Bearer token required')


async def worker():
    while True:
        try:
            await asyncio.to_thread(run)
        except Exception as exc:
            event('', 'run_error', type(exc).__name__)
        try:
            minutes = max(5, int(config().get('interval_minutes', 360)))
        except Exception:
            minutes = 5
        await asyncio.sleep(minutes * 60)


@asynccontextmanager
async def lifespan(app):
    if len(os.getenv('API_TOKEN', '')) < 24:
        raise RuntimeError('Set API_TOKEN to a random secret of at least 24 characters')
    config()
    task = asyncio.create_task(worker())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(title='Job Automation', lifespan=lifespan, dependencies=[Depends(auth)])


@app.get('/jobs')
def jobs():
    return rows()


@app.post('/run')
def trigger():
    return run()


@app.get('/excel')
def download():
    path = root() / 'jobs.xlsx'
    if not path.exists():
        raise HTTPException(404, 'Run collection first')
    return FileResponse(path, filename='jobs.xlsx')


@app.get('/health')
def health():
    return {'status': 'ok'}


@app.post('/jobs/{job_id}/retry')
def retry(job_id: str):
    if not LOCK.acquire(blocking=False):
        raise HTTPException(409, 'Worker is running')
    try:
        with db() as conn:
            job = conn.execute('SELECT * FROM jobs WHERE id=?', (job_id,)).fetchone()
            if not job:
                raise HTTPException(404, 'Job not found')
            if job['status'] not in ('needs_profile', 'needs_review', 'error'):
                raise HTTPException(409, 'Only unsubmitted review/error jobs can be retried; reconcile uncertain submissions manually')
            conn.execute("UPDATE jobs SET status='discovered', updated=? WHERE id=?", (now(), job_id))
        event(job_id, 'retry_requested')
        excel()
        return {'status': 'queued'}
    finally:
        LOCK.release()
