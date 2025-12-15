import express from "express";
import { getSatelliteName } from "./satellite.service";

const router = express.Router();

router.get("/satellite-name", async (req, res) => {
  try {
    const name = await getSatelliteName();
    res.json({ name });
  } catch (err) {
    res.status(500).json({ error: "Satellite fetch failed" });
  }
});

export default router;
