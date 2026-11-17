# CoreXY Wiring - Revision 0

Date: 2026-11-02. Preliminary connection plan; exact carrier pin positions, component ratings and current settings remain open.

CURRENT UPDATE (2026-11-16): User selected DM5, interpreted as DM542T, and wants a custom PCB. The TMC2209-specific diagrams and support wiring below are historical and must not be used as the DM542T schematic. See PCBDesign.md. Magnet choice remains open.

## Design basis

- UNO Q using its 3.3 V MCU digital headers.
- Two CoreXY motors A/B, each with its own driver.
- TMC2209 carrier modules proposed in STEP/DIR mode, subject to motor current and carrier thermal capability. DRV8825 is an alternative requiring different support wiring.
- Tool selection reopened on 2026-11-16: permanent magnet with servo lift versus WF-P34/18 electromagnet. Existing diagrams show only the permanent-magnet candidate.
- X and Y home inputs initially. Remaining switches can be spares or additional travel limits.
- 24 V motor rail proposed, subject to actual module limits and transient margin. Servo voltage separately regulated to its specification.
- UNO Q powered through a suitable USB-C source for initial tests.

## Power connections

```mermaid
flowchart TD
    PSU["Proposed 24 V DC supply"] --> MAIN["Main fuse + DC-rated actuator disconnect"]
    MAIN --> DIST["Positive distribution block"]
    DIST --> FA["Branch fuse A"] --> DA["Driver A VM / VMOT"]
    DIST --> FB["Branch fuse B"] --> DB["Driver B VM / VMOT"]
    DIST --> FS["Servo branch fuse"] --> BUCK["Buck regulator: servo-rated output"]
    BUCK -->|"Servo V+"| SERVO["Lift servo"]
    USB["Suitable USB-C source"] --> Q["UNO Q"]
    DA -->|"Four coil wires"| MA["Motor A"]
    DB -->|"Four coil wires"| MB["Motor B"]
    GND["Common DC ground block"] --- PSU
    GND --- DA
    GND --- DB
    GND --- BUCK
    GND --- SERVO
    GND --- Q
```

Ground lines above mean negative/ground terminals only. Use a non-isolated buck, or explicitly bond its output negative to signal ground if an isolated unit is selected. Return motor/servo currents to the ground distribution block through rated conductors, rather than through UNO Q headers. Protective earth is separate from signal ground; follow the supply's enclosure/earth instructions.

The actuator disconnect removes power from the drivers and servo regulator. Select it for DC load interruption. Firmware must keep drivers disabled after power removal/reboot until deliberately rearmed and rehomed, since carriage position may have been lost.

Place bulk capacitance close to each driver's motor supply terminals. TMC2209 manufacturer guidance recommends at least 100 uF near the driver; account for the carrier's existing capacitance. Final capacitance and voltage rating depend on module limits, wire length and transients. A 50 V electrolytic is a candidate for a 24 V rail, not a guarantee of driver protection. Add servo-side capacitance per regulator/servo requirements.

## Signal connections

```mermaid
flowchart LR
    Q["UNO Q MCU digital headers"] -->|"D2 A_STEP / D5 A_DIR"| A["Driver A"]
    Q -->|"D3 B_STEP / D6 B_DIR"| B["Driver B"]
    Q -->|"D8 shared enable, active LOW"| A
    Q -->|"D8 shared enable, active LOW"| B
    Q -->|"3.3 V to compatible carrier VIO"| A
    Q -->|"3.3 V to compatible carrier VIO"| B
    Q -->|"D9 servo pulses"| BUF["Buffer if required by servo"]
    BUF --> S["Servo signal input"]
    X["X home, verified 3.3 V interface"] -->|"D10"| Q
    Y["Y home, verified 3.3 V interface"] -->|"D11"| Q
```

All signals share the ground described above. Servo power comes from its regulator. If its input accepts 3.3 V, connect D9 directly; otherwise use a non-inverting buffer with a 3.3 V-compatible input and a servo-compatible output level.

### Proposed MCU pin assignments

Logical header labels below are provisional; MCU timer/library compatibility still requires validation on UNO Q.

| UNO Q pin | Net | Connection |
|---|---|---|
| D2 | A_STEP | Driver A STEP |
| D5 | A_DIR | Driver A DIR |
| D3 | B_STEP | Driver B STEP |
| D6 | B_DIR | Driver B DIR |
| D8 | MOTORS_EN_N | Both active-low enable inputs |
| D9 | SERVO_SIGNAL | Servo input; buffer if needed |
| D10 | X_HOME | X home interface |
| D11 | Y_HOME | Y home interface |
| 3V3 | LOGIC_3V3 | Compatible TMC2209 VIO, switch pull-ups |
| GND | SIGNAL_GND | Common ground |

For the proposed TMC2209 design, add an external enable pull-up to 3.3 V so motors remain disabled while MCU pins are high impedance. Start with 10 kohm, checking onboard resistors on the selected carrier. Initialize STEP LOW and directions before enabling. Keep STEP inputs defined at startup, adding pulldowns if required by the carrier.

### Driver support connections to finalize

- Verify carrier manufacturer/revision, orientation, VM limits, VIO pin, sense resistors and continuous cooling capability. Similar carrier footprints do not establish interchangeability.
- Set identical commanded microstep resolution on both channels; specify MS/mode pin straps in the final schematic.
- Set coil current from the actual motor rating and carrier's current-setting method. Distinguish peak from RMS; no VREF value is assigned yet.
- UART is omitted from this draft. Confirm standalone current and mode operation on the actual TMC2209 carrier before enabling motors.
- DRV8825 substitution requires a revised diagram: nRESET/nSLEEP high for operation and MODE pin straps. The Pololu DRV8825 carrier has no external VIO/VDD supply pin. Do not connect 3.3 V to a presumed VIO position.
- Identify the motor's two coil pairs by continuity with power off. Connect one pair to each driver output bridge using the carrier's labels; do not rely on wire colors. Remove power before plugging/unplugging motors.

### Home input details

The PDF's limit-switch link names a three-wire RAMPS-style endstop module. Inspect its electronics and connector order; 3.3 V operation, output level and NC behavior are unverified.

For accessible bare switch contacts, use the following proposed circuit independently for each axis:

```text
UNO Q 3V3 --- 4.7 kohm ---+--- UNO Q home input
                          |
                          +--- switch NC contact
UNO Q GND -------------------- switch COM contact
```

The normally closed contact holds the input LOW when clear. Triggering the switch or opening its cable yields HIGH. Firmware treats HIGH as triggered/fault and debounces the input. This detects open circuits but not all failure types. If using module electronics instead, replace this circuit with the verified 3.3 V-compatible module interface. Add filtering as needed after checking noise and homing response.

## Electrical BOM still to resolve

| Item | Required information |
|---|---|
| Two stepper motors | Model, phase current, resistance, inductance, lead arrangement, step angle |
| Two driver carriers | Selected type, manufacturer/revision, schematic and cooling needs |
| One lift servo | Exact model, voltage, stall current, control threshold and pulse limits; PDF link names MG996R but does not verify the supplied unit |
| Two home inputs | Actual module/contact wiring and output circuit |
| Motor supply | Voltage/current from simultaneous operating loads and driver input power |
| Servo regulator | Output voltage and continuous/transient capacity including stall/start demand |
| Distribution | Fuses, DC disconnect, blocks, rated connectors, wire sizes and strain relief |
| Driver support | Bulk capacitors, cooling, mode straps, enable pull-up |
| Servo interface | Buffer if required, decoupling and rated carriage harness |

The PDF lists five motors, two servos and six switches as shopping quantities. This base design installs two motors, one servo and two home inputs. More actuators require more channels and a revised power budget.

## PCB recommendation

Use assembled modules mounted securely, with terminal blocks or rated connectors for power. Avoid solderless breadboards for motor/servo current. Test both motor channels, coordinated CoreXY moves, homing and loaded servo motion first. A custom carrier PCB can later consolidate driver sockets, connectors, protection, pull-ups, mode straps and capacitance. Existing driver/regulator modules remain suitable building blocks.

## Initial verification

1. Check polarity and regulator output before connecting loads.
2. Verify coil pairs, carrier orientation, current limits and cooling.
3. Confirm motors remain disabled through MCU startup; verify home input states before homing.
4. Test individual motors slowly, then small coordinated X/Y moves to verify signs and belt routing.
5. Test servo lift without forcing linkage stops; check for controller resets or false switch triggers.

## Sources

- Local parts/mechanical reference: C:/Users/reach/Downloads/Brainstorm Dump.pdf, pages 1-3. User confirmed permanent magnet and servo lift on 2026-11-02.
- [CoreXY principle](https://corexy.com/theory.html)
- [UNO Q pinout](https://docs.arduino.cc/resources/pinouts/ABX00162-full-pinout.pdf)
- [UNO Q power specifications](https://docs.arduino.cc/tutorials/uno-q/power-specification)
- [TMC2209 manufacturer datasheet](https://www.analog.com/media/en/technical-documentation/data-sheets/TMC2209_datasheet_rev1.09.pdf)
- [Pololu DRV8825 carrier documentation](https://www.pololu.com/product/2133/)

## Product-link review (2026-11-02)

- Servo: PDF links to https://www.amazon.com/dp/B09JWK494C (MG996R two-pack). Seller specifies 4.8-7.2 V operation and recommends 5 V with 3 A supply capability. Set the draft servo rail to **5 V regulated**, with **at least 3 A available for the single lift servo**, verified for transients and cooling. This is a supply design target, not a claim of continuous servo current. The listing does not establish a guaranteed 3.3 V input threshold, so retain the conditional signal buffer.
- Endstops: https://www.amazon.com/dp/B07PCN6T6F is the linked REIFENG RAMPS-style module. The listing's switch contact ratings do not establish the PCB logic supply or output level. The guaranteed 3.3 V interface and connector order remain unresolved; retain the conditional bare-contact circuit only if those contacts are accessible.
- Stepper row: rechecked PDF page 1 text and hyperlink annotations. The NEMA 17 row has no product hyperlink or model; its quantity is five. Adjacent links belong to spacers and belts. Motor current cannot be obtained from that row.
- Drivers, DC supply and servo regulator have no product rows/links in the PDF. These still require selection.

These findings supersede the generic servo voltage/current placeholders above. The motor rail remains provisional.

## Motor inventory supplied by user (2026-11-02)

These are model/part numbers rather than unique serial numbers. Quantities per model are not yet known.

| Supplied model | Verified phase current | Holding torque | Step angle | Status |
|---|---:|---:|---:|---|
| 17HS16-2004S1 | 2.0 A | 45 Ncm | 1.8 degrees | Manufacturer datasheet located |
| 17HE15-1504S | 1.5 A | 42 Ncm | 1.8 degrees | Manufacturer product specifications located |
| 17HD48002-22B, Bulkman 3D label | 1.7 A provisional | >=56 Ncm provisional | 1.8 degrees provisional | Bulkman NEMA 17 catalog match; page does not explicitly name this model |
| 17HS19-2004S1 | 2.0 A | 59 Ncm | 1.8 degrees | Model spelling confirmed by user |

Manufacturer sources:
- https://www.omc-stepperonline.com/download/17HS16-2004S1.pdf
- https://www.omc-stepperonline.com/e-series-nema-17-bipolar-42ncm-59-49oz-in-1-5a-42x42x38mm-4-wires-w-1m-cable-connector-17he15-1504s
- https://www.omc-stepperonline.com/nema-17-bipolar-59ncm-84oz-in-2a-42x48mm-4-wires-w-1m-cable-connector-17hs19-2004s1

Wiring consequence: choose a matched pair if available. Mixed motors can be commissioned with separate current settings and conservative acceleration, but matching models simplifies balancing CoreXY performance. Do not set a TMC RMS current parameter directly to a motor's nameplate current without checking the motor/driver current conventions and carrier thermal rating.

Coil pairs from manufacturer sources: 17HS16-2004S1 and the likely 17HS19-2004S1 use black/green and red/blue. 17HE15-1504S uses black/blue and green/red. Verify continuity on actual cables; these models are not interchangeable by wire color order.


### Bulkman identification update

User confirmed the 17HD48002-22B motor carries Bulkman 3D branding and corrected the fourth model to 17HS19-2004S1.

Bulkman's own NEMA 17 product page lists 1.7 A DC per phase, 1.8 degrees, 1.8 ohm winding resistance, 3.8 mH inductance, holding torque >=0.56 Nm and a 5 mm shaft. Source: https://bulkman3d.com/product/ec0001-ec0002/

That page uses SKU N17SM-48-5 rather than explicitly naming 17HD48002-22B. These are therefore provisional catalog-match specifications for the user's branded motor, not an exact-model datasheet verification. Do not infer wire colors or final connector order from this match. The listed 3.06 V is the winding DC rating; a higher-voltage supply is used only through a correctly configured current-regulating driver.

### Motor quantities and provisional selection

User reports two of each of the four models (eight motors total). Use the matched 17HS19-2004S1 pair as the provisional CoreXY A/B baseline. Its 59 Ncm holding torque is the highest published holding torque among these candidates; this does not establish a payload or running torque rating. Final acceleration/speed requires load testing or torque-speed analysis. Driver selection must account for its 2 A/phase motor rating, RMS/peak conventions and actual module cooling capability.

## Tool selection update (2026-11-16)

The user is still deciding between a permanent magnet and an electromagnet, and owns a WF-P34/18 electromagnet. This supersedes earlier statements that the permanent-magnet tool is final. Verify the actual unit label for coil voltage, current/power and duty cycle; the model alone does not establish these ratings. The electromagnet requires a separately rated switching stage with inductive transient suppression. Component selection remains open pending those ratings. The matched 17HS19-2004S1 CoreXY motor baseline is independent of this decision.


WF-P34/18 label details supplied by user: DC 24 V, 180 N nominal holding force. Coil current/wattage and duty rating remain unknown; 180 N is a force rating and does not establish electrical consumption or force across the intended working gap. Verify performance with the actual target and intervening surface before final tool selection.

