import plotly.express as px


class ChartGenerator:
    """Creates the Plotly charts as HTML snippets. Takes plain Python data."""

    COLORS = {
        "Recyclable": "#207657",
        "Compostable": "#a3bc5c",
        "Residual waste": "#7e9290",
        "Special handling": "#db9b4b",
        "Unknown": "#bf6556",
    }
    LABELS = {"recyclable": "Recyclable", "compostable": "Compostable", "landfill": "Residual waste",
              "special": "Special handling", "unknown": "Unknown"}

    def _to_html(self, fig):
        fig.update_layout(template="plotly_white", margin=dict(l=12, r=16, t=22, b=27), height=270,
                          font=dict(color="#254439", family="system-ui"),
                          paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        return fig.to_html(full_html=False, include_plotlyjs=False,
                           default_width="100%", config={"responsive": True, "displayModeBar": False})

    def composition_pie(self, counts):
        if not counts:
            return ""
        names = [self.LABELS.get(category, category.title()) for category in counts]
        fig = px.pie(names=names, values=list(counts.values()),
                     color=names, color_discrete_map=self.COLORS, hole=0.4)
        fig.update_traces(textinfo="percent", hovertemplate="%{label}: %{value}<extra></extra>")
        fig.update_layout(legend=dict(orientation="h", x=.5, xanchor="center", y=-.07))
        return self._to_html(fig)

    def top_items_bar(self, top_items):
        if not top_items:
            return ""
        fig = px.bar(x=[count for _, count in top_items],
                     y=[name for name, _ in top_items],
                     orientation="h", color_discrete_sequence=["#207657"],
                     labels={"x": "Count", "y": ""})
        fig.update_layout(yaxis={"categoryorder": "total ascending"})
        return self._to_html(fig)

    def daily_line(self, daily):
        if not daily:
            return ""
        fig = px.line(x=[day for day, _ in daily], y=[count for _, count in daily],
                      markers=True, color_discrete_sequence=["#207657"],
                      labels={"x": "Date", "y": "Count"})
        # One recorded day should show its date, not a millisecond-scale time axis.
        fig.update_xaxes(type="category")
        fig.update_yaxes(rangemode="tozero", dtick=max(1, (max(count for _, count in daily) + 4) // 5))
        return self._to_html(fig)
