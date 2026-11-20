export const sampleChannels = {
  vibration: { unit: "mm/s", value: 2 },
  temperature: { unit: "degC", value: 70 },
  pressure: { unit: "bar", value: 5 },
  flow: { unit: "m3/h", value: 120 },
} as const;
export function sampleRecords(
  sensors: { id: string; channel: string; unit: string }[],
  batch: string,
  observed: number,
) {
  if (
    sensors.length !== 4 ||
    new Set(sensors.map((sensor) => sensor.channel)).size !== 4
  )
    throw new Error("Four distinct canonical channels are required.");
  if (!Number.isFinite(observed) || observed <= 0)
    throw new Error("A valid observation time is required.");
  return Object.entries(sampleChannels).map(([channel, sample]) => {
    const sensor = sensors.find((sensor) => sensor.channel === channel);
    if (!sensor || sensor.unit !== sample.unit)
      throw new Error(
        "Unexpected sensor mapping. Refresh the gateway and inspect its asset.",
      );
    return {
      sensor_id: sensor.id,
      message_id: `${batch}-${channel}`,
      observed_at: observed,
      raw_value: sample.value,
      raw_unit: sample.unit,
      quality: "good",
    };
  });
}
