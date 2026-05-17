// MongoDB init script — seed product catalog
// Runs automatically on first container start via docker-entrypoint-initdb.d

db = db.getSiblingDB("product_db");

db.products.drop();

db.products.insertMany([
  {
    product_id: "p1001",
    name: "Mechanical Keyboard",
    price: 799.0,
    currency: "DKK"
  },
  {
    product_id: "p1002",
    name: "Wireless Mouse",
    price: 299.0,
    currency: "DKK"
  },
  {
    product_id: "p1003",
    name: "USB-C Docking Station",
    price: 1199.0,
    currency: "DKK"
  }
]);

db.products.createIndex({ product_id: 1 }, { unique: true });

print("product_db seeded with " + db.products.countDocuments() + " products.");
