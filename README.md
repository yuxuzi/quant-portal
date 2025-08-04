# quant-portal

A Python project template

## 🚀 Features

- Clean, modern Python project structure
- Comprehensive development tooling
- Easy-to-use CLI
- Robust testing and type checking

## 📦 Installation

```bash
# Using pip
pip install quant_portal

# Using uv
uv pip install quant_portal
```

## 🔧 Development Setup

1. Clone the repository
2. Create a virtual environment
```bash
uv venv
. .venv/bin/activate
```

3. Install dependencies
```bash
make setup
```

## 💻 Usage

### CLI Commands

```bash
# Show help
quant_portal --help

# Hello command
quant_portal hello --name World

# Project info
quant_portal info
```

## 🧪 Testing

Run tests with comprehensive coverage:

```bash
make test
```

## 📝 Development Workflow

- `make lint`: Run code linters
- `make format`: Auto-format code
- `make test`: Run tests
- `make docs`: Generate documentation

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## 📄 License

MIT License

## 👥 Authors

- leoliu <your@email.com>




import pandas as pd
from sqlalchemy import create_engine, text
from datetime import date

# ----------------------
# Configuration
# ----------------------
ORACLE_USER = 'your_user'
ORACLE_PASSWORD = 'your_password'
ORACLE_DSN = 'your_host:1521/your_service'  # e.g. 'localhost:1521/XEPDB1'

# Create engine
engine = create_engine(f'oracle+oracledb://{ORACLE_USER}:{ORACLE_PASSWORD}@{ORACLE_DSN}')

# ----------------------
# Create schema objects
# ----------------------
ddl = """
BEGIN
  EXECUTE IMMEDIATE 'DROP TABLE t1';
EXCEPTION WHEN OTHERS THEN NULL; END;
/
BEGIN
  EXECUTE IMMEDIATE 'DROP TABLE t2';
EXCEPTION WHEN OTHERS THEN NULL; END;
/

CREATE TABLE t1 (
  id NUMBER,
  name VARCHAR2(100),
  query_date DATE
);

CREATE TABLE t2 (
  id NUMBER,
  name VARCHAR2(100),
  query_date DATE
);

INSERT INTO t1 VALUES (1, 'Alice', DATE ''2025-01-01'');
INSERT INTO t1 VALUES (2, 'Bob',   DATE ''2025-02-01'');
INSERT INTO t2 VALUES (3, 'Alice', DATE ''2024-01-01'');
INSERT INTO t2 VALUES (4, 'Carol', DATE ''2024-02-01'');

COMMIT;

BEGIN
  EXECUTE IMMEDIATE 'DROP FUNCTION get_rows_by_date_and_names';
EXCEPTION WHEN OTHERS THEN NULL; END;
/

CREATE OR REPLACE FUNCTION get_rows_by_date_and_names(
  p_cutoff IN DATE,
  p_names IN SYS.ODCIVARCHAR2LIST
)
RETURN SYS.ODCIVARCHAR2LIST PIPELINED
AS
BEGIN
  IF p_cutoff > DATE '2025-01-01' THEN
    FOR r IN (
      SELECT id || ',' || name || ',' || TO_CHAR(query_date, 'YYYY-MM-DD') AS row_str
      FROM t1
      WHERE name IN (SELECT COLUMN_VALUE FROM TABLE(p_names))
        AND query_date > p_cutoff
    ) LOOP
      PIPE ROW(r.row_str);
    END LOOP;
  ELSE
    FOR r IN (
      SELECT id || ',' || name || ',' || TO_CHAR(query_date, 'YYYY-MM-DD') AS row_str
      FROM t2
      WHERE name IN (SELECT COLUMN_VALUE FROM TABLE(p_names))
        AND query_date <= p_cutoff
    ) LOOP
      PIPE ROW(r.row_str);
    END LOOP;
  END IF;
  RETURN;
END;
/
"""

# Execute DDLs
with engine.begin() as conn:
    for stmt in ddl.strip().split("/\n"):
        conn.exec_driver_sql(stmt)

# ----------------------
# Python function to call Oracle
# ----------------------
def call_function(cutoff_date, name_list):
    # Convert list to SYS.ODCIVARCHAR2LIST SQL text
    name_args_sql = ", ".join(f"'{name}'" for name in name_list)
    query = f"""
        SELECT COLUMN_VALUE AS result_row FROM TABLE(
          get_rows_by_date_and_names(
            TO_DATE(:cutoff, 'YYYY-MM-DD'),
            SYS.ODCIVARCHAR2LIST({name_args_sql})
          )
        )
    """

    with engine.connect() as conn:
        df = pd.read_sql(text(query), conn, params={"cutoff": cutoff_date.strftime('%Y-%m-%d')})

    # Parse result string back into columns
    df[['id', 'name', 'query_date']] = df['RESULT_ROW'].str.split(',', expand=True)
    df.drop(columns=['RESULT_ROW'], inplace=True)
    return df

    ```# dashboards/taipy_app.py
from taipy.gui import Gui
from flask import after_this_request

df = ...  # your data
page = "<|{df}|table|>"

gui = Gui(page)

# Hook into Flask app before running
flask_app = gui._server._flask

@flask_app.after_request
def remove_frame_options(response):
    # Option 1: Remove header
    response.headers.pop("X-Frame-Options", None)

    # Option 2: Or allow embedding from same origin
    # response.headers["X-Frame-Options"] = "SAMEORIGIN"

    return response

gui.run()
Perfect — if your Taipy dashboard is same-origin (e.g., served at http://localhost:5000 and your FastAPI+Jinja2 app is http://localhost:8000), then you control both and can allow embedding in an <iframe> easily.

⸻

✅ Goal

You want to embed Taipy in a Jinja2 page like this:

<iframe src="http://localhost:5000" style="width:100%; height:90vh;"></iframe>


⸻

❌ Problem (by default):

Taipy uses Flask under the hood and likely sends this header:

X-Frame-Options: DENY

Which blocks iframe embedding.

⸻

✅ Solution: Remove or modify X-Frame-Options from Taipy’s Flask app

🔧 1. Get the underlying Flask app

If you’re running Taipy via:

Gui(page).run()

Then you can access the underlying Flask app and modify its response headers before it starts.

⸻

✅ 2. Set X-Frame-Options: SAMEORIGIN or remove it

Here’s a full working example:

# dashboards/taipy_app.py
from taipy.gui import Gui
from flask import after_this_request

df = ...  # your data
page = "<|{df}|table|>"

gui = Gui(page)

# Hook into Flask app before running
flask_app = gui._server._flask

@flask_app.after_request
def remove_frame_options(response):
    # Option 1: Remove header
    response.headers.pop("X-Frame-Options", None)

    # Option 2: Or allow embedding from same origin
    # response.headers["X-Frame-Options"] = "SAMEORIGIN"

    return response

gui.run()
<iframe src="http://localhost:5000" style="width:100%; height:90vh;"></iframe>

```

⸻

✅ Now, embed it in your FastAPI page:

index.html

<iframe src="http://localhost:5000" style="width:100%; height:90vh; border:none;"></iframe>


⸻

🔐 Optional: Set Content-Security-Policy

If you’re using strict security headers in your main FastAPI app, ensure:

Content-Security-Policy: frame-ancestors 'self' http://localhost:8000 http://localhost:5000;


⸻

✅ Summary

Task	How to Solve
Allow same-origin iframe embedding	Remove or relax X-Frame-Options in Flask
Embed Taipy into FastAPI Jinja2	Use <iframe src="..."> in a template


⸻

Would you like to:
	•	Serve both apps (FastAPI + Taipy) under the same port and prefix (e.g. /taipy)?
	•	Bundle them into one uvicorn process with mount()?

Let me know how tightly integrated you want this.


# ----------------------
# Example usage
# ----------------------
if __name__ == '__main__':
    names = ['Alice', 'Bob']
    cutoff = date(2025, 2, 1)
    df = call_function(cutoff, names)
    print(df)



