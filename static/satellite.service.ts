export async function getSatelliteName() {
  const satellite = await prisma.satellite.findFirst({
    select: {
      name: true,
    },
  });

  if (!satellite) {
    throw new Error("No satellite found");
  }

  return satellite.name;
}
