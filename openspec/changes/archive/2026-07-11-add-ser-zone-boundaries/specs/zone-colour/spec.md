## MODIFIED Requirements

### Requirement: MadridZoneType maps each zone type to its canonical colour
`MadridZoneType` SHALL override `colour` and return a deterministic, distinct hex string per variant: `Azul` → `#2563EB`, `Verde` → `#16A34A`, `Naranja` → `#F97316`, `Rojo` → `#DC2626`, `AltaRotacion` → `#7C3AED`. No variant SHALL fall back to the grey default — grey is reserved for unrecognised/unmapped zone types via the `ZoneType` base class fallback, not for a known Madrid variant that simply hadn't been assigned a colour yet.

#### Scenario: Azul zone returns blue
- **WHEN** `colour` is accessed on `MadridZoneType.Azul`
- **THEN** the returned value is `"#2563EB"`

#### Scenario: Verde zone returns green
- **WHEN** `colour` is accessed on `MadridZoneType.Verde`
- **THEN** the returned value is `"#16A34A"`

#### Scenario: Naranja zone returns orange
- **WHEN** `colour` is accessed on `MadridZoneType.Naranja`
- **THEN** the returned value is `"#F97316"`

#### Scenario: Rojo zone returns red
- **WHEN** `colour` is accessed on `MadridZoneType.Rojo`
- **THEN** the returned value is `"#DC2626"`

#### Scenario: Alta Rotacion zone returns a distinct colour, not grey
- **WHEN** `colour` is accessed on `MadridZoneType.AltaRotacion`
- **THEN** the returned value is `"#7C3AED"`, not the `"#6B7280"` grey fallback
