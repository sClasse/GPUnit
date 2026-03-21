import pandas as pd  # Import pandas library for data manipulation and analysis
from dash import Dash, dcc, html, Input, Output  # Import Dash components for building the web app
#import plotly.express as px  # Import Plotly Express for quick plotting (though not used here)
from plotly.subplots import make_subplots  # Import for creating subplots in Plotly
import plotly.graph_objects as go  # Import Plotly Graph Objects for detailed chart creation
from dateutil.relativedelta import relativedelta  # Import for relative date calculations
import numpy as np  # Import NumPy for numerical operations

# -------------------------
# LOAD & CLEAN DATA
# -------------------------

def load_data(csv_path):
    df = pd.read_csv(csv_path)

    # Parse 'Sale Date' in format like '12-Nov-23'
    df['Sale Date'] = pd.to_datetime(df['Sale Date'], errors='coerce')

    # Clean 'Price' column to ensure it's numeric
    df['Price'] = pd.to_numeric(df['Price'], errors='coerce')

    # Clean 'Shipping' column to ensure it's numeric
    df['Shipping'] = pd.to_numeric(df['Shipping'], errors='coerce')

    # Clean 'Details' text (standardize case)
    df['Details'] = df['Details'].str.strip().str.lower()

    # Drop any rows missing essential data
    df = df.dropna(subset=['Sale Date', 'Price', 'Type', 'Details'])

    #Add shipping to price
    df['Price'] = df['Price'] + df['Shipping']

    return df

def gpu_table(df):
    return html.Table([
        html.Tr([html.Th(col) for col in df.columns])] + [  # Create table header row with column names
        html.Tr([html.Td(str(cell)) for cell in row]) for row in df.values  # Create table data rows
    ])

# Load cleaned dataset
df = load_data("GPU Cleaned.csv")

# Pull options from data for dropdowns  # Comment for extracting dropdown options
available_conditions = sorted(df['Details'].unique())  # Get unique sorted conditions for dropdown
available_types = sorted(df['Type'].unique())  # Get unique sorted types for dropdown

# Calculate default start date: three months ago, first day of month  # Comment for default date calculation
today = pd.Timestamp.today()  # Get today's date as a timestamp
default_start = (today - relativedelta(months=3)).replace(day=1)  # Calculate start date as first day of month three months ago
default_end = df['Sale Date'].max()  # Set default end date as the maximum sale date in data

# ------------------------- NEW: PRE-COMPUTE TABLES FOR ALL GPU TYPES (LAST 3 MONTHS, ALL CONDITIONS) -------------------------  # Section header for pre-computing tables
three_months_ago = pd.Timestamp.today() - relativedelta(months=3)  # Calculate date three months ago
recent_df = df[df['Sale Date'] >= three_months_ago]  # Filter DataFrame for recent sales
gpu_tables_content = []  # Initialize list to hold table content
for typ in available_types:  # Loop through each GPU type
    sub_df = recent_df[recent_df['Type'] == typ]  # Filter recent data for current type
    if not sub_df.empty:  # Check if there's data for this type
        summary = sub_df.groupby('Details').agg(  # Group by details and aggregate
            Average_Price=('Price', 'mean'),  # Calculate average price
            Total_Volume=('ID', 'count')  # Count total volume
        ).reset_index()  # Reset index
        summary['Average_Price'] = summary['Average_Price'].round(2)  # Round average price to 2 decimals
        summary = summary.rename(columns={'Details': 'Condition'})  # Rename column
        table = gpu_table(summary)  # Create HTML table from summary
        gpu_tables_content.append(html.Div([html.H3(f"Summary for {typ}"), table], style={'marginRight': '20px', 'minWidth': '300px', 'border': '1px solid #ddd', 'padding': '10px', 'borderRadius': '5px'}))  # Group header and table in a div with border
if not gpu_tables_content:  # If no content, add a message
    gpu_tables_content = [html.P("No data available for the last 3 months.")]  # Default message

# -------------------------  # Section header for Dash app setup
# DASH APP SETUP  # Comment for app setup
# -------------------------  # End of section header

app = Dash(__name__)  # Create a Dash app instance
app.title = "GPU Sales Dashboard"  # Set the app title

# App layout  # Comment for layout definition
app.layout = html.Div([  # Define the app layout as a Div
    html.H1("GPU Three Month Average Price"),  # Main title

    html.H2("GPU Market Trends Dashboard"),  # Subtitle

    # Filters container
    html.Div([
        # Smoothing / Aggregation toggle
        html.Div([
            html.Label("Smoothing / Aggregation:"),  # Label for dropdown
            dcc.Dropdown(  # Create dropdown component
                id='smoothing-toggle',  # Unique ID
                options=[  # Options for dropdown
                    {'label': 'None (Daily)', 'value': 'none'},  # Option for no smoothing
                    {'label': '7-day Rolling Average', 'value': '7d'},  # Option for 7-day average
                    {'label': 'Weekly Average', 'value': 'weekly'},  # Option for weekly average
                    {'label': 'Monthly Average', 'value': 'monthly'}  # Option for monthly average
                ],
                value='none',  # Default value
                clearable=False  # Prevent clearing
            ),
        ], style={'flex': '1', 'minWidth': '200px', 'marginRight': '10px'}),

        # Filter by Condition (e.g., used, parts)
        html.Div([
            html.Label("Condition(s):"),  # Label for condition dropdown
            dcc.Dropdown(  # Create condition dropdown
                id='condition-filter',  # Unique ID
                options=[{'label': c.title(), 'value': c} for c in available_conditions],  # Options from available conditions
                value=['used'],  # Default value
                multi=True  # Allow multiple selections
            ),
        ], style={'flex': '1', 'minWidth': '200px', 'marginRight': '10px'}),

        # Filter by GPU Type
        html.Div([
            html.Label("GPU Type(s):"),  # Label for type dropdown
            dcc.Dropdown(  # Create type dropdown
                id='type-filter',  # Unique ID
                options=[{'label': t, 'value': t} for t in available_types],  # Options from available types
                value=[available_types[0]],  # Default to first type
                multi=True  # Allow multiple selections
            ),
        ], style={'flex': '1', 'minWidth': '200px', 'marginRight': '10px'}),

        # Filter by date
        html.Div([
            html.Label("Date Range:"),  # Label for date picker
            dcc.DatePickerRange(  # Create date range picker
                id='date-range',  # Unique ID
                start_date=default_start,  # Default start date
                end_date=default_end,  # Default end date
                min_date_allowed=df['Sale Date'].min(),  # Minimum allowed date
                max_date_allowed=df['Sale Date'].max(),  # Maximum allowed date
                display_format='MMM D, YYYY'  # Display format
            ),
        ], style={'flex': '1', 'minWidth': '250px'}),
    ], style={'display': 'flex', 'flexWrap': 'wrap', 'marginBottom': '20px'}),

    # Average metrics display  # Comment for average price display
    html.Div(id='avg-price', style={'fontWeight': 'bold', 'fontSize': 18, 'marginBottom': '10px'}),  # Div for average price
    html.Div(id='avg-volume', style={'fontWeight': 'bold', 'fontSize': 18, 'marginBottom': '20px'}),  # Div for average volume

    # Output chart  # Comment for graph component
    dcc.Graph(id='gpu-line-chart'),  # Graph component for the chart

    # Static tables for all GPU types (last 3 months, all conditions)  # Comment for tables section
    html.H2("GPU Type Summaries (Avg Price & Volume per Condition - Last 3 Months)"),  # Header for tables
    html.Div(gpu_tables_content, style={'display': 'flex', 'flexWrap': 'wrap'})  # Div containing the pre-computed tables
])

# -------------------------  # Section header for callback
# CALLBACK: INTERACTIVE UPDATE  # Comment for callback function
# -------------------------  # End of section header

@app.callback(  # Decorator for Dash callback
    Output('gpu-line-chart', 'figure'),  # Output to update the chart
    Output('avg-price', 'children'),  # Output to update average price text
    Output('avg-volume', 'children'),  # Output to update average volume text
    Input('smoothing-toggle', 'value'),  # Input from smoothing dropdown
    Input('condition-filter', 'value'),  # Input from condition filter
    Input('type-filter', 'value'),  # Input from type filter
    Input('date-range', 'start_date'),  # Input from start date
    Input('date-range', 'end_date')  # Input from end date
)
def update_chart(smoothing, selected_conditions, selected_types, start_date, end_date):  # Define callback function
    # Filter dataset  # Comment for filtering data
    filtered = df[  # Filter the DataFrame
        (df['Details'].isin(selected_conditions)) &  # Filter by selected conditions
        (df['Type'].isin(selected_types)) &  # Filter by selected types
        (df['Sale Date'] >= pd.to_datetime(start_date)) &  # Filter by start date
        (df['Sale Date'] <= pd.to_datetime(end_date))  # Filter by end date
    ].copy()  # Make a copy

    # Time aggregation period  # Comment for time aggregation
    if smoothing == 'weekly':  # If weekly smoothing
        filtered.loc[:, 'Period'] = filtered['Sale Date'].dt.to_period('W').apply(lambda r: r.start_time)  # Set period to week start
    elif smoothing == 'monthly':  # If monthly smoothing
        filtered.loc[:, 'Period'] = filtered['Sale Date'].dt.to_period('M').apply(lambda r: r.start_time)  # Set period to month start
    else:  # Otherwise
        filtered.loc[:, 'Period'] = filtered['Sale Date']  # Use original date

    # Add Sales Volume column  # Comment for adding volume column
    filtered.loc[:, 'Sales Volume'] = 1  # Set sales volume to 1 per row

    # Group by time, type, and condition  # Comment for grouping data
    price_grouped = filtered.groupby(['Period', 'Type', 'Details'])['Price'].mean().reset_index()  # Group and average price
    volume_grouped = filtered.groupby(['Period', 'Type', 'Details'])['Sales Volume'].sum().reset_index()  # Group and sum volume

    # Add legend label  # Comment for adding legend
    price_grouped.loc[:, 'Legend'] = price_grouped['Type'] + " (" + price_grouped['Details'].str.title() + ")"  # Create legend for price
    volume_grouped.loc[:, 'Legend'] = volume_grouped['Type'] + " (" + volume_grouped['Details'].str.title() + ")"  # Create legend for volume

    # Apply rolling average if selected  # Comment for rolling average
    if smoothing == '7d':  # If 7-day rolling
        smoothed_price = []  # List for smoothed price groups
        smoothed_volume = []  # List for smoothed volume groups
        for name, group in price_grouped.groupby('Legend'):  # Loop through price groups
            group = group.sort_values('Period').copy()  # Sort group by period
            group.loc[:, 'Price'] = group['Price'].rolling(window=7, min_periods=1).mean()  # Apply rolling mean
            smoothed_price.append(group)  # Add to list
        for name, group in volume_grouped.groupby('Legend'):  # Loop through volume groups
            group = group.sort_values('Period').copy()  # Sort group by period
            group.loc[:, 'Sales Volume'] = group['Sales Volume'].rolling(window=7, min_periods=1).mean()  # Apply rolling mean
            smoothed_volume.append(group)  # Add to list
        price_grouped = pd.concat(smoothed_price)  # Concatenate smoothed price
        volume_grouped = pd.concat(smoothed_volume)  # Concatenate smoothed volume

    # Calculate averages  # Comment for calculating averages
    avg_price = filtered['Price'].mean()  # Calculate average price
    avg_volume = filtered['Sales Volume'].sum() / filtered['Period'].nunique() if filtered['Period'].nunique() > 0 else 0  # Calculate average daily volume

    avg_price_text = f"Average Price: ${avg_price:,.2f}"  # Format average price text
    avg_volume_text = f"Average Daily Volume: {avg_volume:,.2f}"  # Format average volume text

    # Create subplots with secondary y-axis  # Comment for creating figure
    fig = make_subplots(specs=[[{"secondary_y": True}]])  # Create subplot with secondary y-axis

    # Add price traces (left y-axis, blue) and trendlines  # Comment for adding price traces
    for legend in price_grouped['Legend'].unique():  # Loop through unique legends
        group = price_grouped[price_grouped['Legend'] == legend]  # Get group for legend
        fig.add_trace(  # Add trace to figure
            go.Scatter(  # Scatter plot
                x=group['Period'],  # X-axis: period
                y=group['Price'],  # Y-axis: price
                mode='lines',  # Line mode
                name=f"{legend} Price",  # Name for legend
                line=dict(color='blue')  # Blue line
            ),
            secondary_y=False  # Primary y-axis
        )
        # Add price trendline  # Comment for trendline
        if len(group) > 1:  # If more than one point
            x = np.arange(len(group))  # X values for polyfit
            y = group['Price'].values  # Y values
            coef = np.polyfit(x, y, 1)  # Fit linear polynomial
            trend = np.poly1d(coef)(x)  # Calculate trend
            fig.add_trace(  # Add trend trace
                go.Scatter(  # Scatter plot for trend
                    x=group['Period'],  # X-axis
                    y=trend,  # Y-axis: trend
                    mode='lines',  # Line mode
                    name=f"{legend} Price Trend",  # Name
                    line=dict(color='purple', dash='dash')  # Purple dashed line
                ),
                secondary_y=False  # Primary y-axis
            )

    # Add volume traces (right y-axis, red) and trendlines  # Comment for adding volume traces
    for legend in volume_grouped['Legend'].unique():  # Loop through unique legends
        group = volume_grouped[volume_grouped['Legend'] == legend]  # Get group for legend
        fig.add_trace(  # Add trace to figure
            go.Scatter(  # Scatter plot
                x=group['Period'],  # X-axis: period
                y=group['Sales Volume'],  # Y-axis: volume
                mode='lines',  # Line mode
                name=f"{legend} Volume",  # Name
                line=dict(color='red')  # Red line
            ),
            secondary_y=True  # Secondary y-axis
        )
        # Add volume trendline  # Comment for volume trendline
        if len(group) > 1:  # If more than one point
            x = np.arange(len(group))  # X values
            y = group['Sales Volume'].values  # Y values
            coef = np.polyfit(x, y, 1)  # Fit polynomial
            trend = np.poly1d(coef)(x)  # Calculate trend
            fig.add_trace(  # Add trend trace
                go.Scatter(  # Scatter plot for trend
                    x=group['Period'],  # X-axis
                    y=trend,  # Y-axis: trend
                    mode='lines',  # Line mode
                    name=f"{legend} Volume Trend",  # Name
                    line=dict(color='orange', dash='dash')  # Orange dashed line
                ),
                secondary_y=True  # Secondary y-axis
            )

    fig.update_layout(  # Update figure layout
        title="GPU Price & Sales Volume Over Time",  # Set title
        hovermode='x unified',  # Unified hover mode
        legend_title='GPU (Condition)'  # Legend title
    )
    fig.update_yaxes(title_text="Average Price (USD)", secondary_y=False)  # Update primary y-axis title
    fig.update_yaxes(title_text="Sales Volume", secondary_y=True)  # Update secondary y-axis title
    fig.update_xaxes(title_text="Date")  # Update x-axis title

    return fig, avg_price_text, avg_volume_text  # Return figure and texts

# -------------------------  # Section header for starting app
# START APP  # Comment for app start
# -------------------------  # End of section header

if __name__ == '__main__':  # If script is run directly
    app.run(debug=True)  # Run the Dash app in debug mode
