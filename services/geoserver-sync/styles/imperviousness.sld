<?xml version="1.0" encoding="UTF-8"?>
<StyledLayerDescriptor version="1.0.0"
    xmlns="http://www.opengis.net/sld"
    xmlns:ogc="http://www.opengis.net/ogc"
    xmlns:xlink="http://www.w3.org/1999/xlink">
  <NamedLayer>
    <Name>imperviousness</Name>
    <UserStyle>
      <Name>imperviousness_style</Name>
      <Title>Imperviousness - Brussels</Title>
      <FeatureTypeStyle>
        <Rule>
          <RasterSymbolizer>
            <ColorMap type="ramp">
              <ColorMapEntry color="#1a9850" quantity="0"   opacity="1" label="Permeable"/>
              <ColorMapEntry color="#91cf60" quantity="51"  opacity="1"/>
              <ColorMapEntry color="#d9ef8b" quantity="102" opacity="1"/>
              <ColorMapEntry color="#fee08b" quantity="152" opacity="1"/>
              <ColorMapEntry color="#fc8d59" quantity="203" opacity="1"/>
              <ColorMapEntry color="#d73027" quantity="254" opacity="1" label="Impervious"/>
            </ColorMap>
          </RasterSymbolizer>
        </Rule>
      </FeatureTypeStyle>
    </UserStyle>
  </NamedLayer>
</StyledLayerDescriptor>
