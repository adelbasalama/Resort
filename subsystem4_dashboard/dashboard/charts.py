import plotly.express as px


class ChartGenerator:
    """Creates the Plotly charts as HTML snippets. Takes plain Python data."""

    COLORS = {
        "recyclable": "#2563eb",   
        "compostable": "#16a34a",  
        "landfill": "#6b7280",    
        "special": "#f59e0b",     
        "unknown": "#dc2626",     
    }

    def _to_html(self, fig):
        fig.update_layout(margin=dict(l=10, r=10, t=50, b=10), height=360)
        return fig.to_html(full_html=False, include_plotlyjs=False,
                           default_width="100%", config={"responsive": True})

    def composition_pie(self, counts):
        if not counts:
            return ""
        names = list(counts.keys())
        fig = px.pie(names=names, values=list(counts.values()), title="Waste composition",
                     color=names, color_discrete_map=self.COLORS, hole=0.4)
        fig.update_traces(textinfo="percent+label")
        fig.update_layout(showlegend=False)
        return self._to_html(fig)

    def top_items_bar(self, top_items):
        if not top_items:
            return ""
        fig = px.bar(x=[count for _, count in top_items],
                     y=[name for name, _ in top_items],
                     orientation="h", title="Top scanned items",
                     labels={"x": "count", "y": ""})
        fig.update_layout(yaxis={"categoryorder": "total ascending"})
        return self._to_html(fig)

    def daily_line(self, daily):
        if not daily:
            return ""
        fig = px.line(x=[day for day, _ in daily], y=[count for _, count in daily],
                      markers=True, title="Items scanned per day",
                      labels={"x": "date", "y": "count"})
        return self._to_html(fig)