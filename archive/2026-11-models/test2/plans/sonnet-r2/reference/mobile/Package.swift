// swift-tools-version:5.9
import PackageDescription

let package = Package(
    name: "CleaningCore",
    platforms: [.iOS(.v16), .macOS(.v13)],
    products: [.library(name: "CleaningCore", targets: ["CleaningCore"])],
    targets: [
        .target(name: "CleaningCore"),
        .testTarget(name: "CleaningCoreTests", dependencies: ["CleaningCore"]),
    ]
)
