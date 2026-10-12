"""Template: places and routes on a map (lat/lon), no external data needed.

Narration bookmarks used: "cities", "route", "far".
Pattern: a faint graticule gives the world's shape; real coordinates place cities;
arcs show routes; distances or numbers attach to the arcs. For coastlines, download
public-domain Natural Earth GeoJSON into workspace/research/ and use geojson_shapes(path).
"""
from waitwhat_style import *

CITIES = {  # name: (lat, lon, label side)  ← real coordinates only
    "London": (51.51, -0.13, UP),
    "New York": (40.71, -74.01, UP),
    "Singapore": (1.35, 103.82, LEFT),
    "Sydney": (-33.87, 151.21, DOWN),
}
W = 12.0


class RoutesMap(WaitwhatScene):
    def construct(self):
        grid = VGroup()
        for lon in range(-180, 181, 30):
            grid.add(Line(latlon(-80, lon, W), latlon(80, lon, W), stroke_width=1, color=INK_4))
        for lat in range(-60, 61, 30):
            grid.add(Line(latlon(lat, -180, W), latlon(lat, 180, W), stroke_width=1 if lat else 2,
                          color=INK_4 if lat else INK_3))
        grid.shift(DOWN * 0.2)
        self.play(Create(grid, lag_ratio=0.02), run_time=1.5)

        dots, labels = {}, VGroup()
        for i, (name, (la, lo, side)) in enumerate(CITIES.items()):
            p = latlon(la, lo, W) + DOWN * 0.2
            dots[name] = Dot(p, radius=0.09, color=CONCEPT_CYCLE[i])
            labels.add(T(name, size=SIZE_SMALL, color=INK).next_to(dots[name], side, buff=0.15))
        self.wait_until("cities")
        self.play(LaggedStart(*[GrowFromCenter(d) for d in dots.values()], lag_ratio=0.2),
                  enter(*labels), run_time=1.6)

        self.wait_until("route")
        legs = [("London", "Singapore"), ("Singapore", "Sydney")]
        arcs = [ArcBetweenPoints(dots[a].get_center(), dots[b].get_center(), angle=-0.5,
                                 color=YELLOW, stroke_width=4) for a, b in legs]
        plane = Dot(color=YELLOW, radius=0.07)
        for arc in arcs:
            self.play(Create(arc), MoveAlongPath(plane, arc), run_time=1.6)
        self.remove(plane)
        self.wait_until("far")
        km = T("≈ 10,900 km", size=SIZE_LABEL, color=YELLOW)
        km.next_to(arcs[0].point_from_proportion(0.45), DL, buff=0.35)
        self.play(enter(km))
        self.finish()
