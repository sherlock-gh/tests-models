// swift-tools-version:5.9
import PackageDescription

let package = Package(
    name: "CleaningKit",
    platforms: [.iOS(.v16), .macOS(.v13)],
    products: [.library(name: "CleaningKit", targets: ["CleaningKit"])],
    targets: [
        .target(name: "CleaningKit"),
        .testTarget(name: "CleaningKitTests", dependencies: ["CleaningKit"]),
    ]
)
