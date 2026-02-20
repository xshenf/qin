const { Sequelize, DataTypes } = require('sequelize');
const path = require('path');

const sequelize = new Sequelize({
    dialect: 'sqlite',
    storage: path.join(__dirname, '../database.sqlite'),
    logging: false
});

const User = sequelize.define('User', {
    id: {
        type: DataTypes.INTEGER,
        autoIncrement: true,
        primaryKey: true
    },
    email: {
        type: DataTypes.STRING,
        allowNull: false,
        unique: true,
        validate: {
            isEmail: true
        }
    },
    password_hash: {
        type: DataTypes.STRING,
        allowNull: false
    },
    role: {
        type: DataTypes.STRING,
        defaultValue: 'user', // 'user' or 'admin'
        allowNull: false
    },
    is_verified: {
        type: DataTypes.BOOLEAN,
        defaultValue: true
    },
    verification_token: {
        type: DataTypes.STRING,
        allowNull: true
    }
});

const HistoryScore = sequelize.define('HistoryScore', {
    id: {
        type: DataTypes.INTEGER,
        autoIncrement: true,
        primaryKey: true
    },
    local_id: {
        type: DataTypes.STRING,
        allowNull: false
    },
    name: {
        type: DataTypes.STRING,
        allowNull: false
    },
    addTime: {
        type: DataTypes.BIGINT,
        allowNull: false
    },
    data: {
        type: DataTypes.BLOB('long'),
        allowNull: false
    }
});

// Relationships
User.hasMany(HistoryScore, { onDelete: 'CASCADE' });
HistoryScore.belongsTo(User);

const initDb = async () => {
    try {
        await sequelize.sync({ alter: true }); // Use { force: true } only for development hard reset
        console.log('Database & tables created!');
    } catch (error) {
        console.error('Unable to create database:', error);
    }
};

module.exports = { sequelize, User, HistoryScore, initDb };
