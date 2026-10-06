from urllib.parse import urlparse

from jobbot.core import db, event, now, root, update


def apply(job, cfg):
    from playwright.sync_api import sync_playwright
    host = urlparse(job['url'] or '').hostname
    adapter = cfg.get('application_adapters', {}).get(host)
    if not adapter or not adapter.get('tested'):
        update(job['id'], status='needs_review', note='No tested application adapter for this host')
        return
    if urlparse(job['url']).scheme != 'https':
        update(job['id'], status='needs_review', note='Application URL must use HTTPS')
        return
    if not adapter.get('confirmation_selector') or not adapter.get('submit_selector'):
        update(job['id'], status='needs_review', note='Missing submit or confirmation selector')
        return
    with db() as conn:
        used = conn.execute("SELECT count(*) FROM events WHERE action='submit_attempt' AND substr(time,1,10)=?", (now()[:10],)).fetchone()[0]
        if used >= cfg.get('daily_limit', 5):
            return
        # Persist intent before any browser activity: a crashed worker is never retried automatically.
        result = conn.execute("UPDATE jobs SET status='applying',updated=? WHERE id=? AND status='prepared'", (now(), job['id']))
        if result.rowcount != 1:
            return
    clicked = False
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                context = browser.new_context()
                def route(request_route):
                    url = urlparse(request_route.request.url)
                    allowed = {host, *adapter.get('resource_hosts', [])}
                    if url.scheme == 'https' and url.hostname in allowed:
                        request_route.continue_()
                    else:
                        request_route.abort()
                context.route('**/*', route)
                page = context.new_page()
                page.set_default_timeout(15000)
                page.goto(job['url'], wait_until='domcontentloaded')
                for selector in adapter.get('blocker_selectors', ['iframe[src*="recaptcha"]', 'iframe[src*="hcaptcha"]']):
                    if page.locator(selector).count():
                        raise ValueError('Challenge requires manual completion')
                for step in adapter.get('steps', []):
                    locator = page.locator(step['selector'])
                    action = step['action']
                    if action == 'upload':
                        locator.set_input_files(job['resume'])
                    else:
                        key = step['profile_key']
                        value = cfg['profile'].get(key, cfg['profile'].get('answers', {}).get(key))
                        if value is None or value == '':
                            raise ValueError(f'Missing approved answer: {key}')
                        if action == 'fill':
                            locator.fill(str(value))
                        elif action == 'select':
                            locator.select_option(label=str(value))
                        elif action == 'check' and isinstance(value, bool):
                            locator.set_checked(value)
                        else:
                            raise ValueError('Unsupported adapter action')
                if page.locator(adapter['confirmation_selector']).count():
                    raise ValueError('Confirmation selector already exists before submission')
                valid = page.locator('form').evaluate_all('(forms) => forms.length > 0 && forms.every(f => f.checkValidity())')
                if not valid:
                    raise ValueError('Required fields are incomplete')
                page.screenshot(path=str(root() / f'{job["id"]}-before.png'), full_page=True)
                event(job['id'], 'submit_attempt')
                clicked = True  # Treat an interrupted click as uncertain too.
                page.locator(adapter['submit_selector']).click()
                page.locator(adapter['confirmation_selector']).wait_for(state='visible', timeout=30000)
                page.screenshot(path=str(root() / f'{job["id"]}-confirmation.png'), full_page=True)
                update(job['id'], status='applied', applied=now(), note='Application confirmation verified')
                event(job['id'], 'applied')
            finally:
                browser.close()
    except Exception as exc:
        status = 'submission_uncertain' if clicked else 'needs_review'
        update(job['id'], status=status, note=str(exc)[:400])
        event(job['id'], status, type(exc).__name__)
