"""Login page rendering for neev.

Uses inline styles because static assets (CSS, JS) are behind auth
and cannot load before the user authenticates.
"""

import html


def render_login_page(error: str | None = None) -> str:
    """Render a self-contained login page matching the Lumina theme.

    Args:
        error: Optional error message to display (e.g., after a failed
            login attempt). Will be HTML-escaped.

    Returns:
        Complete HTML page as a string.
    """
    error_html = ""
    if error:
        escaped = html.escape(error)
        error_html = (
            '<div style="background:#FEF0EE;border:1px solid #FACBC5;'
            "color:#C93425;padding:10px 14px;border-radius:8px;"
            'font-size:0.875rem;margin-bottom:20px;text-align:center">'
            f"{escaped}</div>"
        )

    return _LOGIN_TEMPLATE.format(error_html=error_html)


_LOGIN_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Sign in &mdash; neev</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

    body {{
      font-family: system-ui, -apple-system, sans-serif;
      background: #EFEBE4;
      color: #332F2A;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: 24px;
      -webkit-font-smoothing: antialiased;
    }}

    .card {{
      background: #FFFFFF;
      border-radius: 12px;
      box-shadow: 0 1px 3px 0 rgba(30, 29, 26, 0.10),
                  0 1px 2px -1px rgba(30, 29, 26, 0.07);
      padding: 40px 36px 36px;
      width: 100%;
      max-width: 380px;
    }}

    .logo {{
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 10px;
      margin-bottom: 28px;
    }}

    .logo-icon {{
      width: 36px;
      height: 36px;
      border-radius: 10px;
      background: linear-gradient(135deg, #5A9A84, #386658);
      display: flex;
      align-items: center;
      justify-content: center;
      box-shadow: 0 1px 3px 0 rgba(30, 29, 26, 0.10);
    }}

    .logo-icon span {{
      color: #FFFFFF;
      font-weight: 700;
      font-size: 16px;
      line-height: 1;
    }}

    .logo-text {{
      font-size: 20px;
      font-weight: 600;
      color: #211E1A;
      letter-spacing: -0.01em;
    }}

    label {{
      display: block;
      font-size: 0.8125rem;
      font-weight: 500;
      color: #635E55;
      margin-bottom: 6px;
    }}

    input[type="text"],
    input[type="password"] {{
      width: 100%;
      padding: 10px 14px;
      font-size: 0.875rem;
      font-family: inherit;
      color: #332F2A;
      background: #F2EFEA;
      border: 1px solid #E5E1DA;
      border-radius: 8px;
      outline: none;
      transition: border-color 0.15s, background-color 0.15s, box-shadow 0.15s;
    }}

    input[type="text"]:hover,
    input[type="password"]:hover {{
      border-color: #D4CFC6;
    }}

    input[type="text"]:focus,
    input[type="password"]:focus {{
      border-color: #5A9A84;
      background: #FFFFFF;
      box-shadow: 0 0 0 3px #F0F6F3;
    }}

    .field {{
      margin-bottom: 18px;
    }}

    button {{
      width: 100%;
      padding: 11px 20px;
      font-size: 0.875rem;
      font-weight: 600;
      font-family: inherit;
      color: #FFFFFF;
      background: linear-gradient(135deg, #5A9A84, #47806D);
      border: none;
      border-radius: 8px;
      cursor: pointer;
      transition: opacity 0.15s, box-shadow 0.15s;
      margin-top: 6px;
    }}

    button:hover {{
      opacity: 0.92;
      box-shadow: 0 2px 8px rgba(71, 128, 109, 0.25);
    }}

    button:focus-visible {{
      outline: 2px solid #5A9A84;
      outline-offset: 2px;
    }}

    button:active {{
      opacity: 0.85;
    }}

    .footer {{
      margin-top: 24px;
      text-align: center;
    }}

    .footer p {{
      font-size: 0.75rem;
      color: #ADA89F;
      letter-spacing: 0.025em;
    }}

    .footer span {{
      font-weight: 500;
      color: #827D74;
    }}
  </style>
</head>
<body>
  <div class="card">
    <div class="logo">
      <div class="logo-icon"><span>K</span></div>
      <span class="logo-text">neev</span>
    </div>

    {error_html}

    <form method="POST" action="/_neev/login">
      <div class="field">
        <label for="username">Username</label>
        <input type="text" id="username" name="username"
               autocomplete="username" autocapitalize="off"
               autofocus required>
      </div>
      <div class="field">
        <label for="password">Password</label>
        <input type="password" id="password" name="password"
               autocomplete="current-password" required>
      </div>
      <button type="submit">Sign in</button>
    </form>
  </div>

  <div class="footer">
    <p>served by <span>neev</span></p>
  </div>
</body>
</html>"""
