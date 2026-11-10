/* Interactive station selection for the Urban Weather config flow. */
(() => {
  "use strict";

  const INITIAL_VIEW_STATIONS = 12;
  const config = JSON.parse(document.getElementById("config").textContent);
  const budget = config.budget;
  const stations = new Map(config.stations.map((station) => [station.id, station]));
  const selected = new Set(config.selected.filter((id) => stations.has(id)));
  const markers = new Map();
  let wind = config.wind;
  let saved = false;

  const $ = (id) => document.getElementById(id);
  const text = (key, values = {}) =>
    (config.text[key] || key).replace(/\{(\w+)\}/g, (match, name) =>
      name in values ? String(values[name]) : match,
    );

  // Same budget rules as StationSelection in selection.py.
  const requestsPerHour = (count, interval) =>
    Math.round(((count + (wind === budget.no_wind ? 0 : 1)) * 60) / interval);
  const fittingInterval = (count) =>
    budget.intervals.find(
      (interval) =>
        interval >= budget.min_interval &&
        requestsPerHour(count, interval) + budget.others <= budget.per_hour,
    ) ?? null;
  const maxStations = () => {
    let best = 0;
    for (let count = 1; count <= budget.max_stations; count += 1) {
      if (fittingInterval(count) !== null) best = count;
    }
    return best;
  };

  const element = (tag, className, content) => {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (content !== undefined) node.textContent = content;
    return node;
  };

  const details = (station) =>
    [
      station.distance,
      station.environment,
      station.elevated ? text("elevated") : null,
      station.recommended ? text("legend_recommended") : null,
    ]
      .filter(Boolean)
      .join(" · ");

  const stationIcon = (station) => {
    const classes = ["station"];
    if (selected.has(station.id)) classes.push("selected");
    else if (selected.size >= maxStations()) classes.push("locked");
    if (station.recommended) classes.push("recommended");
    if (station.elevated) classes.push("elevated");
    return L.divIcon({
      className: classes.join(" "),
      iconSize: [30, 30],
      html: `<span>${station.number}</span>`,
    });
  };

  const tooltip = (station) => {
    const node = element("div");
    node.append(element("div", "tip-title", `${station.number} · ${station.label}`));
    node.append(element("div", null, details(station)));
    return node;
  };

  const showStatus = (message, isError = false) => {
    const status = $("status");
    status.textContent = message;
    status.classList.toggle("error", isError);
  };

  const toggle = (id) => {
    if (saved) return;
    if (selected.has(id)) {
      selected.delete(id);
    } else if (selected.size >= maxStations()) {
      showStatus(text("limit_reached", { max: maxStations() }), true);
      return;
    } else {
      selected.add(id);
    }
    showStatus("");
    render();
  };

  const renderList = () => {
    const list = $("selected");
    list.replaceChildren();
    [...selected]
      .map((id) => stations.get(id))
      .sort((a, b) => a.number - b.number)
      .forEach((station) => {
        const item = element("li");
        item.append(element("span", "number", String(station.number)));
        const body = element("div", "text");
        body.append(element("div", null, station.label));
        body.append(element("div", "muted", details(station)));
        item.append(body);
        const remove = element("button", null, "×");
        remove.type = "button";
        remove.title = text("remove");
        remove.addEventListener("click", () => toggle(station.id));
        item.append(remove);
        list.append(item);
      });
  };

  const render = () => {
    markers.forEach((marker, id) => {
      marker.setIcon(stationIcon(stations.get(id)));
      marker.setZIndexOffset(selected.has(id) ? 1000 : 0);
    });
    const max = maxStations();
    const interval = fittingInterval(selected.size);
    $("counter").textContent = text("counter", { count: selected.size, max });
    renderList();
    if (selected.size > max || interval === null) {
      $("budget").textContent = text("over_budget");
    } else if (selected.size) {
      $("budget").textContent = text("budget", {
        interval,
        requests: requestsPerHour(selected.size, interval) + budget.others,
        budget: budget.per_hour,
      });
    } else {
      $("budget").textContent = text("none_selected");
    }
    $("submit").disabled =
      saved || selected.size === 0 || selected.size > max || interval === null;
  };

  const submit = async () => {
    $("submit").disabled = true;
    showStatus(text("saving"));
    try {
      const response = await fetch(window.location.pathname, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ temperature_sensors: [...selected], wind_sensor: wind }),
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(result.error || response.status);
      saved = true;
      render();
      showStatus(text("done"));
      window.setTimeout(() => window.close(), 1500);
    } catch (error) {
      showStatus(text("error", { error: error.message }), true);
      $("submit").disabled = false;
    }
  };

  const buildLegend = () => {
    const entries = [
      ["station selected", "legend_selected"],
      ["station recommended", "legend_recommended"],
      ["station", "legend_other"],
      ["station elevated", "legend_elevated"],
      ["home", "legend_home"],
    ];
    const legend = $("legend");
    entries.forEach(([className, key]) => {
      const item = element("li");
      item.append(element("span", className));
      item.append(element("span", null, text(key)));
      legend.append(item);
    });
  };

  const buildWindSelect = () => {
    const select = $("wind");
    config.wind_options.forEach((option) => {
      const node = element("option", null, option.label);
      node.value = option.value;
      node.selected = option.value === wind;
      select.append(node);
    });
    select.addEventListener("change", () => {
      wind = select.value;
      render();
    });
  };

  const buildMap = () => {
    const map = L.map("map");
    L.tileLayer(config.tiles.url, {
      attribution: config.tiles.attribution,
      maxNativeZoom: 18,
      maxZoom: 19,
    }).addTo(map);
    L.circle(config.home, {
      radius: config.radius,
      color: "#db3236",
      weight: 2,
      dashArray: "6 6",
      fill: false,
      interactive: false,
    }).addTo(map);
    L.marker(config.home, {
      // Leaflet positions markers via transform, so rotate an inner element.
      icon: L.divIcon({
        className: "home-marker",
        iconSize: [20, 20],
        html: '<div class="home"></div>',
      }),
      title: text("legend_home"),
      zIndexOffset: -1000,
    }).addTo(map);
    config.stations.forEach((station) => {
      const marker = L.marker([station.lat, station.lon], {
        icon: stationIcon(station),
        title: `${station.number} · ${station.label}`,
        riseOnHover: true,
      });
      marker.bindTooltip(tooltip(station), { direction: "top", offset: [0, -14] });
      marker.on("click", () => toggle(station.id));
      marker.addTo(map);
      markers.set(station.id, marker);
    });
    // Start close enough to tell nearby markers apart; the radius may be cut off.
    const bounds = L.latLngBounds([config.home, config.home]);
    config.stations
      .filter((station) => station.number <= INITIAL_VIEW_STATIONS || selected.has(station.id))
      .forEach((station) => bounds.extend([station.lat, station.lon]));
    map.fitBounds(bounds, { padding: [40, 40] });
  };

  document.title = text("title");
  $("title").textContent = text("title");
  $("recommendation").textContent = config.recommendation;
  $("hint").textContent = text("hint");
  $("wind-label").textContent = text("wind");
  $("submit").textContent = text("submit");
  $("submit").addEventListener("click", submit);
  buildWindSelect();
  buildLegend();
  buildMap();
  render();
})();
