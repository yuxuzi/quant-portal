# app.py
import logging
from functools import wraps

import dash
import pandas as pd
import plotly.express as px
from dash import dcc, html
from dash.dependencies import Input, Output
from flask import Flask, flash, redirect, render_template, request, session, url_for
from taipy.gui import Gui

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Initialize Flask application
app = Flask(__name__)
# app.config.from_object('config')


# Sample data for dashboards
def create_sample_data():
    # Create a sample dataframe for demonstration
    df = pd.DataFrame(
        {
            "Date": pd.date_range(start="2023-01-01", periods=100),
            "Sales": [100 + i * 2 + (i % 7) * 10 for i in range(100)],
            "Customers": [50 + i + (i % 5) * 8 for i in range(100)],
            "Region": pd.Series(["North", "South", "East", "West"]).sample(
                100, replace=True
            ),
        }
    )
    return df


df = create_sample_data()

# Initialize Dash application
dash_app = dash.Dash(
    __name__,
    server=app,
    routes_pathname_prefix="/dash/",
    serve_locally=True,  
)

# Use Dash auth middleware to protect Dash routes
dash_app.layout = html.Div(
    [
        html.H1("Dash Dashboard"),
        html.Div(
            [
                dcc.Dropdown(
                    id="region-dropdown",
                    options=[
                        {"label": region, "value": region}
                        for region in df["Region"].unique()
                    ],
                    value=df["Region"].unique()[0],
                    clearable=False,
                ),
                dcc.Graph(id="sales-graph"),
                dcc.Graph(id="customers-graph"),
            ]
        ),
    ]
)


# Define Dash callbacks
@dash_app.callback(
    [Output("sales-graph", "figure"), Output("customers-graph", "figure")],
    [Input("region-dropdown", "value")],
)
def update_graphs(selected_region):
    filtered_df = df[df["Region"] == selected_region]

    sales_fig = px.line(
        filtered_df, x="Date", y="Sales", title=f"Sales Trends in {selected_region}"
    )

    customers_fig = px.bar(
        filtered_df,
        x="Date",
        y="Customers",
        title=f"Customer Count in {selected_region}",
    )

    return sales_fig, customers_fig


# Protect Dash routes


# Taipy application setup
def create_taipy_app():
    # Define Taipy data and pages
    sales_data = df.copy()

    # Chart building function
    def build_chart(state):
        if state.selected_chart == "Monthly Sales":
            monthly_data = (
                state.sales_data.groupby(state.sales_data["Date"].dt.month)["Sales"]
                .sum()
                .reset_index()
            )
            return px.bar(monthly_data, x="Date", y="Sales", title="Monthly Sales")
        else:
            return px.pie(
                state.sales_data,
                names="Region",
                values="Customers",
                title="Customer Distribution by Region",
            )

    # Define page content
    taipy_root_page = """
        <h1>Taipy Dashboard</h1>
        <|{selected_chart}|toggle|lov=Monthly Sales;Customer Distribution|on_change=build_chart|>
        <br/>
        <|{chart}|>
        """

    taipy_about_page = """
        <h1>About Taipy Dashboard</h1>
        <p>This is a sample Taipy dashboard integrated within a Flask application.</p>
        """

    # Initialize state
    data = {"sales_data": sales_data, "selected_chart": "Monthly Sales", "chart": None}

    # Create and configure Taipy app
    taipy_app = Gui(
        pages={
            "taipy2": taipy_root_page,
            "taipy1": taipy_about_page,
        },
        flask=app
     
    )

    # Register callbacks

    return taipy_app, data


# Create Taipy app
taipy_app, taipy_data = create_taipy_app()



# Protect Taipy routes
# @app.before_request
# def protect_taipy():
#     if request.path.startswith("/taipy") and not session.get("authenticated"):
#         return redirect(url_for("login", next=request.url))


# Authentication routes
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        # Authentication is handled by Kerberos decorator
        # At this point, the user is already authenticated
        username = request.environ.get("REMOTE_USER", "").split("@")[0]
        session["authenticated"] = True
        session["username"] = username
        logger.info(f"User {username} successfully logged in")

        # Redirect to the next parameter or home page
        next_page = request.args.get("next", url_for("index"))
        return redirect(next_page)

    return render_template("login.html", title="Login")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out successfully.")
    return redirect(url_for("login"))


# Flask routes
@app.route("/")
def index():
    #username = session.get("username", "User")
    return render_template(
        "index.html",
        title="Dashboard Portal",
        user_name="Leo",
        apps=[
            {"name": "Flask Home", "url": url_for("index")},
            {"name": "Dash Dashboard", "url": url_for("dash_dashboard")},
            {"name": "Taipy Dashboard", "url": url_for("taipy_dashboard")},
            {"name": "About", "url": url_for("about")},
            {"name": "Logout", "url": url_for("logout")},
        ],
    )


@app.route("/about")
def about():
    username = session.get("username", "User")
    return render_template(
        "about.html",
        title="About",
        username=username,
        apps=[
            {"name": "Flask Home", "url": url_for("index")},
            {"name": "Dash Dashboard", "url": url_for("dash_dashboard")},
            {"name": "Taipy Dashboard", "url": url_for("taipy_dashboard")},
            {"name": "About", "url": url_for("about")},
            {"name": "Logout", "url": url_for("logout")},
        ],
    )


@app.route("/dash-dashboard")
def dash_dashboard():
    return redirect("/dash/")


@app.route("/taipy-dashboard")
def taipy_dashboard():
    return redirect("/taipy1/")


# Error handlers
@app.errorhandler(401)
def unauthorized(error):
    flash("Authentication failed. Please try again.")
    return redirect(url_for("login"))


@app.errorhandler(403)
def forbidden(error):
    flash("You don't have permission to access this resource.")
    return redirect(url_for("login"))


@app.errorhandler(500)
def server_error(error):
    logger.error(f"Server error: {error}")
    return render_template("error.html", error=error), 500


# Run the application
if __name__ == "__main__":
    #    print("Starting server on port 5000...")
    #app.run(port=5000)
    taipy_app.run(initial_state=taipy_data, port=5001)
