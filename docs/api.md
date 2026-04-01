# API Documentation

## Endpoints

### User Balance

- **GET** `/api/users/{user_id}/balance`
  - Get a user's coin balance
  - Response: `{ "balance": 1000 }`

### Update Balance

- **POST** `/api/users/{user_id}/balance`
  - Update a user's coin balance
  - Body: `{ "amount": 100 }`
  - Response: `{ "new_balance": 1100 }`

## Authentication

All API requests require a valid Discord token in the Authorization header.
