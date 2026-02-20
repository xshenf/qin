const express = require('express');
const router = express.Router();
const { HistoryScore } = require('../db');
const { verifyToken } = require('../middleware/auth');

// Sync history to backend
router.post('/sync', verifyToken, async (req, res) => {
    try {
        const userId = req.userId;
        const { history } = req.body;

        if (!Array.isArray(history)) {
            return res.status(400).json({ message: 'Invalid history format' });
        }

        // Loop through the provided history array from frontend
        for (const item of history) {
            const { id, name, addTime, data } = item;

            // Check if this history item already exists
            const existing = await HistoryScore.findOne({
                where: { UserId: userId, local_id: id }
            });

            if (existing) {
                // Update time if changed. Also update data if provided.
                existing.addTime = addTime;
                existing.name = name;
                if (data) {
                    existing.data = Buffer.from(data, 'base64');
                }
                await existing.save();
            } else {
                // Create new record
                await HistoryScore.create({
                    UserId: userId,
                    local_id: id,
                    name,
                    addTime,
                    data: data ? Buffer.from(data, 'base64') : Buffer.alloc(0)
                });
            }
        }

        res.json({ message: 'History synced successfully' });
    } catch (error) {
        console.error('Error syncing history:', error);
        res.status(500).json({ message: 'Server error' });
    }
});

// Get user history
router.get('/', verifyToken, async (req, res) => {
    try {
        const userId = req.userId;
        const history = await HistoryScore.findAll({
            where: { UserId: userId },
            order: [['addTime', 'DESC']],
            attributes: ['id', 'local_id', 'name', 'addTime'] // Exclude heavy data blob for listing
        });

        res.json(history);
    } catch (error) {
        console.error('Error fetching history:', error);
        res.status(500).json({ message: 'Server error' });
    }
});

// Get specific history score data
router.get('/:localId/data', verifyToken, async (req, res) => {
    try {
        const userId = req.userId;
        const { localId } = req.params;

        const score = await HistoryScore.findOne({
            where: { UserId: userId, local_id: localId }
        });

        if (!score) {
            return res.status(404).json({ message: 'Score not found' });
        }

        res.json({ data: score.data.toString('base64') });
    } catch (error) {
        console.error('Error fetching score data:', error);
        res.status(500).json({ message: 'Server error' });
    }
});

module.exports = router;
