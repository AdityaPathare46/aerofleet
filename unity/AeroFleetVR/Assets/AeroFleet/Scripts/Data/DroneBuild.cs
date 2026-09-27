using System;

namespace AeroFleet.VR.Data
{
    /// <summary>
    /// A multirotor assembled from catalogue parts, with first-order performance numbers. Every model
    /// and constant is stated here and on the board — this is a sizing sketch, not a flight test:
    ///
    ///   all-up mass   frame + motors + ESCs + avionics + battery + payload
    ///   hover power   actuator-disc momentum theory, P_ideal = sqrt((m g)^3 / (2 rho A)), A = n pi r^2,
    ///                 divided by an assumed rotor figure of merit (0.60) and motor+ESC efficiency (0.80),
    ///                 plus 8 W for avionics
    ///   endurance     usable energy (80 % of rated Wh — the rest is the landing reserve) / hover power
    ///   thrust/weight sum of the motors' rated maximum static thrust on the frame's prop / weight;
    ///                 below 1.6 the drone can hover but has no margin to manoeuvre or fight wind
    ///   DGCA category by all-up weight, Drone Rules 2021: nano ≤ 250 g, micro ≤ 2 kg, small ≤ 25 kg,
    ///                 medium ≤ 150 kg, large above
    ///
    /// Part figures are representative of their class (typical datasheet values), not a specific SKU.
    /// </summary>
    public class DroneBuild
    {
        public const double G = 9.81, Rho = 1.225, FigureOfMerit = 0.60, DriveEfficiency = 0.80, AvionicsW = 8, UsableFraction = 0.80;
        public const double AvionicsKg = 0.12, EscKg = 0.018;
        public const double MinThrustToWeight = 1.6;

        public struct Frame { public string Name; public double Kg; public int Arms; public double PropInch; }
        public struct Motor { public string Name; public double Kg; public double MaxThrustKgf; public double MaxPropInch; }
        public struct Battery { public string Name; public double Kg; public int Cells; public double Ah; public double Wh => Cells * 3.7 * Ah; }

        public static readonly Frame[] Frames =
        {
            new Frame { Name = "250 mm quad · 5\" props", Kg = 0.12, Arms = 4, PropInch = 5 },
            new Frame { Name = "450 mm quad · 10\" props", Kg = 0.28, Arms = 4, PropInch = 10 },
            new Frame { Name = "650 mm delivery quad · 15\" props", Kg = 0.85, Arms = 4, PropInch = 15 },
            new Frame { Name = "960 mm delivery hexa · 17\" props", Kg = 1.9, Arms = 6, PropInch = 17 },
        };

        public static readonly Motor[] Motors =
        {
            new Motor { Name = "2207 · 1950 kV", Kg = 0.033, MaxThrustKgf = 1.2, MaxPropInch = 5.5 },
            new Motor { Name = "2216 · 880 kV", Kg = 0.070, MaxThrustKgf = 1.0, MaxPropInch = 11 },
            new Motor { Name = "4114 · 400 kV", Kg = 0.150, MaxThrustKgf = 2.6, MaxPropInch = 16 },
            new Motor { Name = "6215 · 180 kV", Kg = 0.340, MaxThrustKgf = 5.5, MaxPropInch = 22 },
        };

        public static readonly Battery[] Batteries =
        {
            new Battery { Name = "4S 1500 mAh LiPo", Kg = 0.18, Cells = 4, Ah = 1.5 },
            new Battery { Name = "4S 5200 mAh LiPo", Kg = 0.52, Cells = 4, Ah = 5.2 },
            new Battery { Name = "6S 10000 mAh Li-ion", Kg = 1.35, Cells = 6, Ah = 10 },
            new Battery { Name = "6S 22000 mAh Li-ion", Kg = 2.70, Cells = 6, Ah = 22 },
        };

        public static readonly double[] Payloads = { 0, 0.5, 1, 2, 3, 5 };

        public int FrameIndex = 2, MotorIndex = 2, BatteryIndex = 2, PayloadIndex = 2;

        public Frame F => Frames[FrameIndex];
        public Motor M => Motors[MotorIndex];
        public Battery B => Batteries[BatteryIndex];
        public double PayloadKg => Payloads[PayloadIndex];

        public void Step(string part, int delta)
        {
            int Wrap(int i, int n) => ((i + delta) % n + n) % n;
            switch (part)
            {
                case "frame": FrameIndex = Wrap(FrameIndex, Frames.Length); break;
                case "motor": MotorIndex = Wrap(MotorIndex, Motors.Length); break;
                case "battery": BatteryIndex = Wrap(BatteryIndex, Batteries.Length); break;
                case "payload": PayloadIndex = Wrap(PayloadIndex, Payloads.Length); break;
            }
        }

        public double EmptyKg => F.Kg + F.Arms * (M.Kg + EscKg) + AvionicsKg + B.Kg;
        public double AllUpKg => EmptyKg + PayloadKg;
        public double DiscAreaM2 => F.Arms * Math.PI * Math.Pow(F.PropInch * 0.0254 / 2, 2);
        public double HoverW
        {
            get
            {
                double thrustN = AllUpKg * G;
                double ideal = Math.Sqrt(thrustN * thrustN * thrustN / (2 * Rho * DiscAreaM2));
                return ideal / FigureOfMerit / DriveEfficiency + AvionicsW;
            }
        }
        public double EnduranceMin => B.Wh * UsableFraction / HoverW * 60;
        public double ThrustToWeight => F.Arms * M.MaxThrustKgf / AllUpKg;
        public bool PropTooBigForMotor => F.PropInch > M.MaxPropInch;

        public string Category =>
            AllUpKg <= 0.25 ? "Nano" : AllUpKg <= 2 ? "Micro" : AllUpKg <= 25 ? "Small" : AllUpKg <= 150 ? "Medium" : "Large";

        /// <summary>What stops this build from flying safely, worst first; empty when none.</summary>
        public string Problem =>
            ThrustToWeight < 1.0 ? "Cannot lift off — the motors' combined thrust is less than the weight."
            : PropTooBigForMotor ? $"{F.PropInch:0}\" props overload the {M.Name} motors (rated to {M.MaxPropInch:0}\")."
            : ThrustToWeight < MinThrustToWeight ? $"Thrust/weight {ThrustToWeight:0.0} is below {MinThrustToWeight:0.0} — it hovers, but has no margin for wind or manoeuvres."
            : EnduranceMin < 5 ? "Under 5 minutes of usable hover — too short for a delivery leg."
            : "";
    }
}
