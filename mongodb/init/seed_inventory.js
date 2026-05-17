// MongoDB init script — seed inventory
// Runs automatically on first container start via docker-entrypoint-initdb.d

db = db.getSiblingDB("inventory_db");

db.inventory.drop();

db.inventory.insertMany([
  { product_id: "p1001", stock: 100 },
  { product_id: "p1002", stock: 100 },
  { product_id: "p1003", stock: 100 }
]);

db.inventory.createIndex({ product_id: 1 }, { unique: true });

print("inventory_db seeded with " + db.inventory.countDocuments() + " items.");
