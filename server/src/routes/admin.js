const express = require('express');
const { User } = require('../db');
const { verifyToken, isAdmin } = require('../middleware/auth');
const router = express.Router();

// List all users
router.get('/users', verifyToken, isAdmin, async (req, res) => {
    try {
        const users = await User.findAll({
            attributes: ['id', 'email', 'role', 'is_verified', 'createdAt']
        });
        res.json(users);
    } catch (error) {
        console.error(error);
        res.status(500).json({ message: 'Server error fetching users.' });
    }
});

// Delete user
router.delete('/users/:id', verifyToken, isAdmin, async (req, res) => {
    try {
        const userId = req.params.id;
        await User.destroy({ where: { id: userId } });
        res.json({ message: 'User deleted successfully.' });
    } catch (error) {
        console.error(error);
        res.status(500).json({ message: 'Server error deleting user.' });
    }
});

module.exports = router;
