## ADDED Requirements

### Requirement: ZoneType exposes a colour property
The `ZoneType` base class SHALL expose a `colour` property that returns a hex colour string representing the zone's visual identity on a map. The base implementation SHALL return `#6B7280` (grey) as the default fallback so that city providers without an override do not raise errors.

#### Scenario: Base class returns grey fallback
- **WHEN** `colour` is accessed on a `ZoneType` instance that has not overridden the property
- **THEN** the returned value is `"#6B7280"`

### Requirement: MadridZoneType maps each zone type to its canonical colour
`MadridZoneType` SHALL override `colour` and return a deterministic hex string per variant: `Azul` → `#2563EB`, `Verde` → `#16A34A`, `AltaRotacion` / `Naranja` / `Rojo` → `#6B7280`.

#### Scenario: Azul zone returns blue
- **WHEN** `colour` is accessed on `MadridZoneType.Azul`
- **THEN** the returned value is `"#2563EB"`

#### Scenario: Verde zone returns green
- **WHEN** `colour` is accessed on `MadridZoneType.Verde`
- **THEN** the returned value is `"#16A34A"`

#### Scenario: Alta Rotacion returns grey
- **WHEN** `colour` is accessed on `MadridZoneType.AltaRotacion`
- **THEN** the returned value is `"#6B7280"`

#### Scenario: Naranja returns grey
- **WHEN** `colour` is accessed on `MadridZoneType.Naranja`
- **THEN** the returned value is `"#6B7280"`

#### Scenario: Rojo returns grey
- **WHEN** `colour` is accessed on `MadridZoneType.Rojo`
- **THEN** the returned value is `"#6B7280"`
