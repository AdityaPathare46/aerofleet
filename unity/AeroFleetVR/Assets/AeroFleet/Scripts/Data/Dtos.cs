using System.Collections.Generic;
using Newtonsoft.Json;

// Mirrors the AeroFleet backend's JSON exactly (aerofleet/api/routes/*.py). Same contract the
// web VR Safety View uses — tauri-app/src/components/vr/types.ts — so both render identical data.
namespace AeroFleet.VR.Data
{
    public class CityDto
    {
        [JsonProperty("slug")] public string Slug;
        [JsonProperty("name")] public string Name;
        [JsonProperty("center")] public double[] Center;
        [JsonProperty("airport_name")] public string AirportName;
    }

    public class ZoneDto
    {
        [JsonProperty("zone_id")] public string ZoneId;
        [JsonProperty("zone_type")] public string ZoneType;   // GREEN | YELLOW | RED
        [JsonProperty("reason")] public string Reason;
        [JsonProperty("center_lat")] public double CenterLat;
        [JsonProperty("center_lon")] public double CenterLon;
        [JsonProperty("radius_m")] public double RadiusM;
    }

    public class DepotDto
    {
        [JsonProperty("depot_id")] public string DepotId;
        [JsonProperty("name")] public string Name;
        [JsonProperty("lat")] public double? Lat;
        [JsonProperty("lon")] public double? Lon;
    }

    /// <summary>Street polylines as flat [east, north, east, north, ...] metres from Center.</summary>
    public class RoadsDto
    {
        [JsonProperty("center")] public double[] Center;
        [JsonProperty("synthetic")] public bool Synthetic;
        [JsonProperty("major")] public List<int[]> Major;
        [JsonProperty("minor")] public List<int[]> Minor;
    }

    /// <summary>OSM buildings: each entry is [height_dm, source_index, e1, n1, e2, n2, ...] metres from Center.</summary>
    public class BuildingsDto
    {
        [JsonProperty("center")] public double[] Center;
        [JsonProperty("available")] public bool Available;
        [JsonProperty("count")] public int Count;
        [JsonProperty("sources")] public List<string> Sources = new List<string>();
        [JsonProperty("height_sources")] public Dictionary<string, int> HeightSources = new Dictionary<string, int>();
        [JsonProperty("assumed_height_m")] public double AssumedHeightM;
        [JsonProperty("attribution")] public string Attribution;
        [JsonProperty("buildings")] public List<int[]> Buildings = new List<int[]>();
    }

    public class LiveDrone
    {
        [JsonProperty("lat")] public double Lat;
        [JsonProperty("lon")] public double Lon;
        [JsonProperty("link_mode")] public string LinkMode;
        [JsonProperty("safety_margins")] public Dictionary<string, double> SafetyMargins;
        [JsonProperty("passed")] public bool Passed;
        [JsonProperty("state")] public string State;
        [JsonProperty("order_id")] public string OrderId;
        [JsonProperty("altitude_m")] public double AltitudeM;
        [JsonProperty("altitude_ceiling_m")] public double AltitudeCeilingM;
        [JsonProperty("zone")] public string Zone;
        [JsonProperty("battery_soc_pct")] public double BatterySocPct;
        [JsonProperty("battery_available_wh")] public double BatteryAvailableWh;
        [JsonProperty("battery_reserve_wh")] public double BatteryReserveWh;
        [JsonProperty("payload_kg")] public double PayloadKg;
        [JsonProperty("nearest_drone_id")] public string NearestDroneId;
        [JsonProperty("nearest_horizontal_m")] public double NearestHorizontalM;
        [JsonProperty("nearest_vertical_m")] public double NearestVerticalM;
        [JsonProperty("heading_deg")] public double? HeadingDeg;
        [JsonProperty("progress")] public double? Progress;
        [JsonProperty("remaining_m")] public double? RemainingM;
        [JsonProperty("arrived")] public bool Arrived;
        [JsonProperty("route")] public List<double[]> Route;
        [JsonProperty("phase")] public string Phase;          // CLIMB | CRUISE | DESCENT | LANDED (null: no plan)
        [JsonProperty("eta_s")] public double? EtaS;          // seconds to touchdown
        /// <summary>Whole flight as [lat, lon, altitude_m, t_rel_s]; negative t = already flown.</summary>
        [JsonProperty("trajectory")] public List<double[]> Trajectory = new List<double[]>();
        [JsonProperty("position_source")] public string PositionSource;
    }

    public class DronePair
    {
        [JsonProperty("a")] public string A;
        [JsonProperty("b")] public string B;
        [JsonProperty("horizontal_m")] public double HorizontalM;
        [JsonProperty("vertical_m")] public double VerticalM;
        [JsonProperty("slant_m")] public double SlantM;
        [JsonProperty("separation_margin_m")] public double SeparationMarginM;
    }

    /// <summary>A pair whose planned trajectories come within the watch band later in the forecast horizon.</summary>
    public class PredictedConflict
    {
        [JsonProperty("a")] public string A;
        [JsonProperty("b")] public string B;
        [JsonProperty("t_s")] public double TS;
        [JsonProperty("horizontal_m")] public double HorizontalM;
        [JsonProperty("vertical_m")] public double VerticalM;
        [JsonProperty("separation_margin_m")] public double SeparationMarginM;
        [JsonProperty("severity")] public string Severity;    // CONFLICT | WATCH
        [JsonProperty("a_at")] public double[] AAt;           // [lat, lon, altitude_m]
        [JsonProperty("b_at")] public double[] BAt;
    }

    public class LiveConstants
    {
        [JsonProperty("min_separation_m")] public double MinSeparationM = 15;
        [JsonProperty("operational_ceiling_m")] public double OperationalCeilingM = 100;
        [JsonProperty("legal_ceiling_m")] public double LegalCeilingM = 120;
        [JsonProperty("pair_awareness_radius_m")] public double PairAwarenessRadiusM = 250;
        [JsonProperty("cruise_speed_mps")] public double CruiseSpeedMps = 12;
        [JsonProperty("climb_rate_mps")] public double ClimbRateMps = 3;
        [JsonProperty("descent_rate_mps")] public double DescentRateMps = 2;
        [JsonProperty("forecast_horizon_s")] public double ForecastHorizonS = 120;
        [JsonProperty("separation_watch_band_m")] public double SeparationWatchBandM = 35;
    }

    public class ConstraintSources
    {
        [JsonProperty("live")] public List<string> Live = new List<string>();
        [JsonProperty("default")] public List<string> Default = new List<string>();
    }

    public class LiveMarginsDto
    {
        [JsonProperty("city")] public string City;
        [JsonProperty("generated_at")] public double GeneratedAt;
        [JsonProperty("drone_count")] public int DroneCount;
        [JsonProperty("drones")] public Dictionary<string, LiveDrone> Drones = new Dictionary<string, LiveDrone>();
        [JsonProperty("pairs")] public List<DronePair> Pairs = new List<DronePair>();
        [JsonProperty("predicted_conflicts")] public List<PredictedConflict> PredictedConflicts = new List<PredictedConflict>();
        [JsonProperty("forecast_drone_ids")] public List<string> ForecastDroneIds = new List<string>();
        [JsonProperty("fleet_worst_case")] public Dictionary<string, double> FleetWorstCase = new Dictionary<string, double>();
        [JsonProperty("constants")] public LiveConstants Constants = new LiveConstants();
        [JsonProperty("constraint_sources")] public ConstraintSources ConstraintSources = new ConstraintSources();
    }

    public class IncidentSummaryDto
    {
        [JsonProperty("incident_id")] public string IncidentId;
        [JsonProperty("city")] public string City;
        [JsonProperty("trigger_type")] public string TriggerType;
        [JsonProperty("status")] public string Status;
        [JsonProperty("created_at")] public string CreatedAt;
    }

    public class LatLonDto
    {
        [JsonProperty("lat")] public double? Lat;
        [JsonProperty("lon")] public double? Lon;
    }

    public class ViolationDto
    {
        [JsonProperty("constraint_name")] public string ConstraintName;
        [JsonProperty("violation_magnitude")] public double ViolationMagnitude;
        [JsonProperty("required_correction")] public double RequiredCorrection;
    }

    public class ClaimRow
    {
        [JsonProperty("factor")] public string Factor;
        [JsonProperty("council_claim")] public string CouncilClaim;
        [JsonProperty("council_confidence")] public double? CouncilConfidence;
        [JsonProperty("implicated_by_geometry")] public bool ImplicatedByGeometry;
        [JsonProperty("evidence_constraints")] public List<string> EvidenceConstraints = new List<string>();
        [JsonProperty("status")] public string Status;
    }

    public class ClaimCheck
    {
        [JsonProperty("rows")] public List<ClaimRow> Rows = new List<ClaimRow>();
        [JsonProperty("counts")] public Dictionary<string, int> Counts = new Dictionary<string, int>();
        [JsonProperty("agrees_with_geometry")] public bool AgreesWithGeometry;
        [JsonProperty("has_council_claims")] public bool HasCouncilClaims;
    }

    public class VrSceneDto
    {
        [JsonProperty("incident_id")] public string IncidentId;
        [JsonProperty("city")] public string City;
        [JsonProperty("drone_id")] public string DroneId;
        [JsonProperty("trigger_type")] public string TriggerType;
        [JsonProperty("status")] public string Status;
        [JsonProperty("position")] public LatLonDto Position;
        [JsonProperty("origin")] public LatLonDto Origin;
        [JsonProperty("altitude_m")] public double? AltitudeM;
        [JsonProperty("max_altitude_m")] public double? MaxAltitudeM;
        [JsonProperty("in_red_zone")] public bool InRedZone;
        [JsonProperty("in_yellow_zone")] public bool InYellowZone;
        [JsonProperty("violations")] public List<ViolationDto> Violations = new List<ViolationDto>();
        [JsonProperty("root_cause_summary")] public string RootCauseSummary;
        [JsonProperty("recommended_action")] public string RecommendedAction;
        [JsonProperty("claim_check")] public ClaimCheck ClaimCheck = new ClaimCheck();
        /// <summary>Route the CBF gate checked, per waypoint: [lat, lon, altitude_m, in_red_zone 0/1, battery_margin_wh].</summary>
        [JsonProperty("planned_route")] public List<double[]> PlannedRoute = new List<double[]>();
    }

    public class TokenDto
    {
        [JsonProperty("access_token")] public string AccessToken;
    }
}
