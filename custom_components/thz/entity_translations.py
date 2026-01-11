"""Translation key mappings for writable THZ entities.

This module provides a mapping from entity internal names (as used in write maps)
to their translation keys. This enables localization of entity names for switches,
numbers, and selects.
"""

# Mapping of entity names to translation keys for writable entities
ENTITY_TRANSLATION_KEYS = {
    # Operating mode
    "pOpMode": "op_mode",
    # Room temperatures HC1
    "p01RoomTempDay": "room_temp_day",
    "p02RoomTempNight": "room_temp_night",
    "p03RoomTempStandby": "room_temp_standby",
    "p01RoomTempDayHC1": "room_temp_day_hc1",
    "p02RoomTempNightHC1": "room_temp_night_hc1",
    "p03RoomTempStandbyHC1": "room_temp_standby_hc1",
    "p01RoomTempDayHC1SummerMode": "room_temp_day_hc1_summer",
    "p02RoomTempNightHC1SummerMode": "room_temp_night_hc1_summer",
    "p03RoomTempStandbyHC1SummerMode": "room_temp_standby_hc1_summer",
    # Room temperatures HC2
    "p01RoomTempDayHC2": "room_temp_day_hc2",
    "p02RoomTempNightHC2": "room_temp_night_hc2",
    "p03RoomTempStandbyHC2": "room_temp_standby_hc2",
    "p01RoomTempDayHC2SummerMode": "room_temp_day_hc2_summer",
    "p02RoomTempNightHC2SummerMode": "room_temp_night_hc2_summer",
    "p03RoomTempStandbyHC2SummerMode": "room_temp_standby_hc2_summer",
    # DHW temperatures
    "p04DHWsetTempDay": "dhw_temp_day",
    "p05DHWsetTempNight": "dhw_temp_night",
    "p06DHWsetTempStandby": "dhw_temp_standby",
    "p11DHWsetTempManual": "dhw_temp_manual",
    # Fan stages
    "p07FanStageDay": "fan_stage_day",
    "p08FanStageNight": "fan_stage_night",
    "p09FanStageStandby": "fan_stage_standby",
    "p12FanStageManual": "fan_stage_manual",
    # Manual mode
    "p10HCTempManual": "hc_temp_manual",
    # Heating curve HC1
    "p13GradientHC1": "gradient_hc1",
    "p14LowEndHC1": "low_end_hc1",
    "p15RoomInfluenceHC1": "room_influence_hc1",
    # Heating curve HC2
    "p16GradientHC2": "gradient_hc2",
    "p17LowEndHC2": "low_end_hc2",
    "p18RoomInfluenceHC2": "room_influence_hc2",
    # Flow proportions
    "p19FlowProportionHC1": "flow_proportion_hc1",
    "p20FlowProportionHC2": "flow_proportion_hc2",
    # Hysteresis settings
    "p21Hyst1": "hysteresis_1",
    "p22Hyst2": "hysteresis_2",
    "p23Hyst3": "hysteresis_3",
    "p24Hyst4": "hysteresis_4",
    "p25Hyst5": "hysteresis_5",
    "p26Hyst6": "hysteresis_6",
    "p27Hyst7": "hysteresis_7",
    "p28Hyst8": "hysteresis_8",
    "p29HystAsymmetry": "hysteresis_asymmetry",
    "p30integralComponent": "integral_component",
    "p31MaxBoostStages": "max_boost_stages",
    "p32HystDHW": "hysteresis_dhw",
    # Booster settings
    "p33BoosterTimeoutDHW": "booster_timeout_dhw",
    "p34TempLimitBoostDHW": "temp_limit_boost_dhw",
    "p79BoosterTimeoutHC": "booster_timeout_hc",
    # Pasteurization
    "p35PasteurisationInterval": "pasteurization_interval",
    "p36MaxDurationDHWLoad": "max_duration_dhw_load",
    # Fan airflow settings
    "p37Fanstage1AirflowInlet": "fan_stage1_airflow_inlet",
    "p38Fanstage2AirflowInlet": "fan_stage2_airflow_inlet",
    "p39Fanstage3AirflowInlet": "fan_stage3_airflow_inlet",
    "p40Fanstage1AirflowOutlet": "fan_stage1_airflow_outlet",
    "p41Fanstage2AirflowOutlet": "fan_stage2_airflow_outlet",
    "p42Fanstage3AirflowOutlet": "fan_stage3_airflow_outlet",
    "p43UnschedVent3": "unsched_vent_3",
    "p44UnschedVent2": "unsched_vent_2",
    "p45UnschedVent1": "unsched_vent_1",
    "p46UnschedVent0": "unsched_vent_0",
    # Compressor and system
    "p47CompressorRestartDelay": "compressor_restart_delay",
    "p48MainFanSpeed": "main_fan_speed",
    "p49SummerModeTemp": "summer_mode_temp",
    "p50SummerModeHysteresis": "summer_mode_hysteresis",
    # Pump cycles
    "p54MinPumpCycles": "min_pump_cycles",
    "p55MaxPumpCycles": "max_pump_cycles",
    "p56OutTempMaxPumpCycles": "out_temp_max_pump_cycles",
    "p57OutTempMinPumpCycles": "out_temp_min_pump_cycles",
    "p58SuppressTempCaptPumpStart": "suppress_temp_capt_pump_start",
    # Passive cooling
    "p75PassiveCooling": "passive_cooling",
    # Filter and temperature
    "p77OutTempFilterTime": "out_temp_filter_time",
    "p78DualModePoint": "dual_mode_point",
    # Solar
    "p80EnableSolar": "enable_solar",
    "p81DiffTempSolarLoading": "diff_temp_solar_loading",
    "p82DelayCompStartSolar": "delay_comp_start_solar",
    "p84DHWTempSolarMode": "dhw_temp_solar_mode",
    "p84EnableDHWBuffer": "enable_dhw_buffer",
}


def get_translation_key(entity_name: str) -> str | None:
    """Get the translation key for an entity name.
    
    Args:
        entity_name: The internal entity name from write_map.
    
    Returns:
        The translation key if found, otherwise None.
    """
    return ENTITY_TRANSLATION_KEYS.get(entity_name)
