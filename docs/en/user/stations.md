# Station recommendation

Dense networks like [Mannheim's](../networks/mannheim.md), with more than 400 stations, have many of them in street
canyons, on roofs or in parks only a few hundred metres apart. Their values differ, so the closest station is not always
the best one for your place.

## Stations

A station is a place with one or more sensor modules: temperature and humidity, often air
pressure and irradiance, and on some masts wind. Modules within 15 m of each other count as
one station. Each station has:

| Property | Source |
|---|---|
| Code, e.g. `0101-046` | Sensor names of the API |
| District | OpenStreetMap |
| Surroundings | Local Climate Zone from the city's metadata catalogue, otherwise from the global LCZ map |
| Roof or high point | Mounting zone and height above ground from the metadata catalogue |

Details: [Stations and reference data](../developer/reference-data.md).

## How the recommendation works

```mermaid
flowchart TD
    All[Temperature stations<br>sorted by distance] --> Street[Leave out stations<br>on roofs and high points]
    Street --> Near{Nearest station at most 1 km away<br>and same surroundings?}
    Near -- yes --> Single[Use it on its own]
    Near -- no --> Radius[Stations within the search radius,<br>the 4 nearest if there are none]
    Radius --> Order[Same surroundings first,<br>then the closest others]
    Order --> Combine[Combine up to 4 stations]
```

- Stations on roofs or high points measure other temperatures than at street level and are
  not recommended for temperature. You can still select them yourself; they are marked
  *roof/high point*.
- The wind station is the nearest station with a wind sensor, wherever it is mounted.
- The reason is shown with the recommendation: the nearest station fits, is too far away
  or has other surroundings.
- In a [network without siting data](#networks-without-siting-data) distance alone decides.
- *Use the recommendation* is not offered if it does not fit the [API budget](api-limits.md),
  for example because other locations already use most of it. Choose fewer stations from the
  map or the list then.

## Networks without siting data

Some networks, such as [Dortmund](../networks/dortmund.md), publish no surroundings or
mounting data.

- The nearest station within 1 km is used on its own; otherwise up to 4 stations within the
  search radius are combined.
- The surroundings you confirm during setup are kept with the location but do not change the
  recommendation.

## Choosing yourself

- **One station** gives exactly its values, including short local effects.
- **Several stations** give their median, which is steadier and closer to the typical value
  of the area. With 4 or more stations, outliers are left out.
- At most 6 stations per location; how many fit depends on the API budget.

## New stations

The city adds stations from time to time. When the daily station list contains stations
that are new within the last 30 days and part of the current recommendation for a location,
a repair issue suggests the new recommendation.

- The selection only changes if you apply the suggestion, because other stations change the
  values (jumps in long-term statistics) and the API budget.
- If you keep your stations, the suggestion is ignored. It only comes back for a different
  suggestion.
- No suggestion appears if the recommendation would not fit the API budget.

See [Repairs and troubleshooting](troubleshooting.md#new-stations-nearby).
