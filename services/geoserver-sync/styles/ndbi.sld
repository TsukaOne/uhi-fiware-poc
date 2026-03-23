<?xml version="1.0" encoding="UTF-8"?>
<StyledLayerDescriptor version="1.0.0"
    xmlns="http://www.opengis.net/sld"
    xmlns:ogc="http://www.opengis.net/ogc"
    xmlns:xlink="http://www.w3.org/1999/xlink">
  <NamedLayer>
    <Name>ndbi</Name>
    <UserStyle>
      <Name>ndbi_style</Name>
      <Title>Normalized Difference Built-Up Index - Brussels</Title>
      <FeatureTypeStyle>
        <Rule>
          <RasterSymbolizer>
            <ColorMap type="ramp">
              <ColorMapEntry color="#1a9641" quantity="0"   opacity="1" label="Vegetation"/>
              <ColorMapEntry color="#a6d96a" quantity="38"  opacity="1"/>
              <ColorMapEntry color="#ffffbf" quantity="64"  opacity="1" label="Neutral"/>
              <ColorMapEntry color="#fdae61" quantity="102" opacity="1"/>
              <ColorMapEntry color="#d73027" quantity="152" opacity="1"/>
              <ColorMapEntry color="#7b0f1a" quantity="254" opacity="1" label="Built-up"/>
            </ColorMap>
          </RasterSymbolizer>
        </Rule>
      </FeatureTypeStyle>
    </UserStyle>
  </NamedLayer>
</StyledLayerDescriptor>
