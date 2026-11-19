// swift-tools-version:5.9
import PackageDescription

let package = Package(
    name: "CleaningLogic",
    platforms: [.iOS(.v16), .macOS(.v13)],
    products: [.library(name: "CleaningLogic", targets: ["CleaningLogic"])],
    targets: [
        .target(name: "CleaningLogic"),
        .testTarget(name: "CleaningLogicTests", dependencies: ["CleaningLogic"]),
    ]
)
